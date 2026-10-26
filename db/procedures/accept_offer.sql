-- AcceptOffer: the host accepts a purchase offer or rental application.
-- Replaces the legacy sell_property flow. Everything happens in one transaction
-- with row locks, so two hosts' clicks or two offers can't both win:
--   1. lock the offer and its listing (SELECT ... FOR UPDATE)
--   2. validate ownership and state, SIGNAL a readable error otherwise
--   3. accept this offer, supersede the other pending ones
--   4. mark the listing sold / rented
--   5. record the transaction with the commission computed here, once
--   6. notify everyone involved
DROP PROCEDURE IF EXISTS AcceptOffer;

DELIMITER $$

CREATE PROCEDURE AcceptOffer(IN p_offer_id BIGINT UNSIGNED, IN p_host_id BIGINT UNSIGNED)
BEGIN
    DECLARE v_listing_id BIGINT UNSIGNED;
    DECLARE v_guest_id   BIGINT UNSIGNED;
    DECLARE v_amount     DECIMAL(12,2);
    DECLARE v_status     VARCHAR(20);
    DECLARE v_owner      BIGINT UNSIGNED;
    DECLARE v_mode       VARCHAR(20);
    DECLARE v_l_status   VARCHAR(20);
    DECLARE v_currency   CHAR(3);
    DECLARE v_title      VARCHAR(140);
    DECLARE v_listing_pid CHAR(26);
    DECLARE v_rate       DECIMAL(5,4);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT o.listing_id, o.guest_id, o.amount, o.status
      INTO v_listing_id, v_guest_id, v_amount, v_status
      FROM offers o WHERE o.id = p_offer_id
      FOR UPDATE;

    IF v_listing_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Offer not found.';
    END IF;

    SELECT host_id, listing_mode, status, currency, title, public_id
      INTO v_owner, v_mode, v_l_status, v_currency, v_title, v_listing_pid
      FROM listings WHERE id = v_listing_id
      FOR UPDATE;

    IF v_owner <> p_host_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Offer not found.';
    END IF;
    IF v_status <> 'pending' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This offer is no longer pending.';
    END IF;
    IF v_l_status <> 'published' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The listing is not available any more.';
    END IF;
    IF v_mode NOT IN ('sale','long_term_rent') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Offers apply only to sales and long-term rentals.';
    END IF;

    SELECT COALESCE(h.commission_rate, CAST(JSON_UNQUOTE(s.v) AS DECIMAL(5,4)), 0.05)
      INTO v_rate
      FROM settings s LEFT JOIN host_profiles h ON h.user_id = p_host_id
      WHERE s.k = 'default_commission_rate';

    UPDATE offers SET status = 'accepted', decided_at = NOW() WHERE id = p_offer_id;

    INSERT INTO notifications (user_id, kind, title, link)
    SELECT guest_id, 'offer_superseded', CONCAT('Your offer on "', v_title, '" was not accepted'),
           CONCAT('/listings/', v_listing_pid)
      FROM offers WHERE listing_id = v_listing_id AND status = 'pending';
    UPDATE offers SET status = 'superseded', decided_at = NOW()
     WHERE listing_id = v_listing_id AND status = 'pending';

    UPDATE listings SET status = IF(v_mode = 'sale', 'sold', 'rented') WHERE id = v_listing_id;

    INSERT INTO transactions (kind, listing_id, host_id, guest_id, offer_id, amount, commission, currency)
    VALUES (IF(v_mode = 'sale', 'sale', 'rental'), v_listing_id, p_host_id, v_guest_id, p_offer_id,
            v_amount, ROUND(v_amount * v_rate, 2), v_currency);

    INSERT INTO notifications (user_id, kind, title, link)
    VALUES (v_guest_id, 'offer_accepted', CONCAT('Your offer on "', v_title, '" was accepted!'), '/trips');

    COMMIT;

    SELECT LAST_INSERT_ID() AS transaction_id, v_amount AS amount, ROUND(v_amount * v_rate, 2) AS commission;
END$$

DELIMITER ;
