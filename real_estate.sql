DROP DATABASE IF EXISTS real_estate;
CREATE DATABASE IF NOT EXISTS real_estate;

USE real_estate;

CREATE TABLE Clients(
	c_name VARCHAR(150) NOT NULL,
	c_username VARCHAR(100) NOT NULL,
    c_password VARCHAR(100) NOT NULL,
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
    agent_password VARCHAR(100) NOT NULL,
    agent_contact VARCHAR(20) NOT NULL,
    PRIMARY KEY(agent_id)
);

CREATE TABLE Property(
	p_id INT NOT NULL,
    p_type ENUM('sale','rent') NOT NULL,
    p_size INT NOT NULL,
    p_price INT NOT NULL,
    p_status ENUM('sold','available') NOT NULL,
    agent_id INT NOT NULL,
    PRIMARY KEY(p_id),
    FOREIGN KEY (agent_id) 	REFERENCES Agent(agent_id)
);

CREATE TABLE Transactions(
    t_id INT NOT NULL,
    commision INT,
    t_date DATE NOT NULL,
    c_username VARCHAR(100) NOT NULL,
    p_id INT NOT NULL,
    agent_id INT NOT NULL,
    PRIMARY KEY (t_id),
    FOREIGN KEY (c_username) REFERENCES Clients(c_username),
    FOREIGN KEY (p_id) REFERENCES Property(p_id),
    FOREIGN KEY (agent_id) REFERENCES Agent(agent_id)
);

CREATE TABLE TransactionLog (
    p_id INT NOT NULL,
    commision DECIMAL(10, 2) NOT NULL,
    t_date DATETIME NOT NULL,
    PRIMARY KEY (p_id),
    FOREIGN KEY (p_id) REFERENCES Property(p_id)
);


DELIMITER $$

CREATE FUNCTION GetMaxAgentId()
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE max_id INT;
    SELECT MAX(agent_id) INTO max_id FROM Agent;
    RETURN IFNULL(max_id, 202400); -- If no agents exist, return the default starting value
END$$

DELIMITER ;

DELIMITER $$

CREATE FUNCTION GetMaxPropertyId()
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE max_id INT;
    SELECT MAX(p_id) INTO max_id FROM Property;
    RETURN IFNULL(max_id, 100); -- Default to 100 if no properties exist
END$$

DELIMITER ;

DELIMITER $$

CREATE PROCEDURE GetProperties(
    IN min_price DECIMAL(10,2),
    IN max_price DECIMAL(10,2),
    IN min_size INT,
    IN max_p_size INT,
    IN property_type VARCHAR(50)
)
BEGIN
    SELECT * 
    FROM Property
    WHERE 
        (
            (min_price IS NULL AND max_price IS NULL) OR
            (p_price BETWEEN min_price AND max_price) 
        )
        AND 
        (
            (min_size IS NULL AND max_p_size IS NULL) OR
            (p_size BETWEEN min_size AND max_p_size)
        )
        AND 
        (
            property_type IS NULL OR p_type = property_type
        );
END$$

DELIMITER ;

DELIMITER $$

CREATE PROCEDURE FilterProperties(
    IN input_agent_id INT,
    IN price_min DECIMAL(10,2),
    IN price_max DECIMAL(10,2),
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

CREATE TRIGGER after_property_sold
AFTER UPDATE ON Property
FOR EACH ROW
BEGIN
	DECLARE commission_rate DECIMAL(5, 2) DEFAULT 0.05;
	DECLARE calculated_commission DECIMAL(10, 2);
    IF NEW.p_status = 'sold' THEN
        -- Calculate commission
        SET calculated_commission = NEW.p_price * commission_rate;
        
        -- Log the commission for external processing
        INSERT INTO TransactionLog (p_id, commision, t_date)
        VALUES (NEW.p_id, calculated_commission, NOW());
    END IF;
END$$

DELIMITER ;

SELECT *
FROM Agent;
