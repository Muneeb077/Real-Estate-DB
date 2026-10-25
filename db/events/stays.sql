DROP EVENT IF EXISTS ev_expire_booking_holds;
DROP EVENT IF EXISTS ev_complete_stays;

DELIMITER $$

-- Unpaid holds release their dates after booking_hold_minutes.
CREATE EVENT ev_expire_booking_holds
ON SCHEDULE EVERY 1 MINUTE
COMMENT 'Expire unpaid booking holds'
DO
BEGIN
    UPDATE bookings SET status = 'expired'
     WHERE status = 'pending' AND hold_expires_at < NOW();
END$$

-- After check-out, a confirmed stay becomes completed and the guest is invited to review.
CREATE EVENT ev_complete_stays
ON SCHEDULE EVERY 1 HOUR
COMMENT 'Complete finished stays and ask for reviews'
DO
BEGIN
    INSERT INTO notifications (user_id, kind, title, link)
    SELECT b.guest_id, 'review_invite', CONCAT('How was your stay at "', l.title, '"? Leave a review'),
           CONCAT('/trips/', b.public_id)
      FROM bookings b JOIN listings l ON l.id = b.listing_id
     WHERE b.status = 'confirmed' AND b.check_out <= CURDATE();
    UPDATE bookings SET status = 'completed'
     WHERE status = 'confirmed' AND check_out <= CURDATE();
END$$

DELIMITER ;
