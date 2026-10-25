DROP DATABASE IF EXISTS real_estate;
CREATE DATABASE IF NOT EXISTS real_estate CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE real_estate;

-- Passwords hold Argon2id hashes (~97 chars), never plaintext.
CREATE TABLE Clients(
	c_name VARCHAR(150) NOT NULL,
	c_username VARCHAR(100) NOT NULL,
    c_password VARCHAR(255) NOT NULL,
    contact VARCHAR(20) NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    city VARCHAR(50) NOT NULL,
    street VARCHAR(50) NOT NULL,
    state VARCHAR(50) NOT NULL,
    PRIMARY KEY(c_username)
);

CREATE TABLE Agent(
	agent_id INT AUTO_INCREMENT NOT NULL,
    agent_name VARCHAR(150) NOT NULL,
    agent_password VARCHAR(255) NOT NULL,
    agent_contact VARCHAR(20) NOT NULL,
    PRIMARY KEY(agent_id)
) AUTO_INCREMENT = 202401;

CREATE TABLE Property(
	p_id INT AUTO_INCREMENT NOT NULL,
    p_type ENUM('sale','rent') NOT NULL,
    p_size INT NOT NULL,
    p_price DECIMAL(12,2) NOT NULL,
    p_status ENUM('sold','available') NOT NULL,
    agent_id INT NOT NULL,
    PRIMARY KEY(p_id),
    FOREIGN KEY (agent_id) 	REFERENCES Agent(agent_id),
    CHECK (p_price > 0),
    CHECK (p_size > 0),
    INDEX idx_property_search (p_status, p_type, p_price),
    INDEX idx_property_agent (agent_id, p_status)
) AUTO_INCREMENT = 100;

CREATE TABLE Transactions(
    t_id INT AUTO_INCREMENT NOT NULL,
    sale_price DECIMAL(12,2) NOT NULL,
    commission DECIMAL(12,2) NOT NULL,
    t_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    c_username VARCHAR(100) NOT NULL,
    p_id INT NOT NULL,
    agent_id INT NOT NULL,
    PRIMARY KEY (t_id),
    UNIQUE KEY uq_transaction_property (p_id),
    FOREIGN KEY (c_username) REFERENCES Clients(c_username),
    FOREIGN KEY (p_id) REFERENCES Property(p_id),
    FOREIGN KEY (agent_id) REFERENCES Agent(agent_id)
);


DELIMITER $$

CREATE PROCEDURE GetProperties(
    IN min_price DECIMAL(12,2),
    IN max_price DECIMAL(12,2),
    IN min_size INT,
    IN max_p_size INT,
    IN property_type VARCHAR(50)
)
BEGIN
    -- Each bound is optional on its own; results are capped for the public page.
    SELECT p_id, p_type, p_size, p_price, p_status, agent_id
    FROM Property
    WHERE p_status = 'available'
        AND (min_price IS NULL OR p_price >= min_price)
        AND (max_price IS NULL OR p_price <= max_price)
        AND (min_size IS NULL OR p_size >= min_size)
        AND (max_p_size IS NULL OR p_size <= max_p_size)
        AND (property_type IS NULL OR p_type = property_type)
    ORDER BY p_price
    LIMIT 500;
END$$

DELIMITER ;

DELIMITER $$

CREATE PROCEDURE FilterProperties(
    IN input_agent_id INT,
    IN price_min DECIMAL(12,2),
    IN price_max DECIMAL(12,2),
    IN size_min INT,
    IN size_max INT,
    IN property_type VARCHAR(50)
)
BEGIN
    SELECT p_id, p_type, p_size, p_price, p_status, agent_id
    FROM Property
    WHERE agent_id = input_agent_id
        AND (p_price >= price_min OR price_min IS NULL)
        AND (p_price <= price_max OR price_max IS NULL)
        AND (p_size >= size_min OR size_min IS NULL)
        AND (p_size <= size_max OR size_max IS NULL)
        AND (p_type = property_type OR property_type IS NULL);
END$$
DELIMITER ;


DELIMITER $$

-- Replaces the old two-step sell (UPDATE commit, then INSERT) and the
-- after_property_sold trigger: the status change and the transaction row are
-- written in one DB transaction, and commission is computed in one place.
CREATE PROCEDURE CompleteSale(
    IN in_p_id INT,
    IN in_agent_id INT,
    IN in_c_username VARCHAR(100),
    IN in_price DECIMAL(12,2)
)
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_owner INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT p_status, agent_id INTO v_status, v_owner
    FROM Property WHERE p_id = in_p_id
    FOR UPDATE;

    IF v_owner IS NULL OR v_owner <> in_agent_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Property not found or not yours.';
    END IF;
    IF v_status = 'sold' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The property is already sold.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM Clients WHERE c_username = in_c_username) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Client username does not exist.';
    END IF;

    UPDATE Property SET p_status = 'sold', p_price = in_price WHERE p_id = in_p_id;

    INSERT INTO Transactions (sale_price, commission, c_username, p_id, agent_id)
    VALUES (in_price, ROUND(in_price * 0.05, 2), in_c_username, in_p_id, in_agent_id);

    COMMIT;
END$$

DELIMITER ;
