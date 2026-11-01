-- Fresh databases only: this script seeds customer data.
-- Run create_users.sql separately to add registration without changing customers.
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

INSERT INTO customers (customer_id, name)
VALUES
    (101, 'John'),
    (102, 'Mary'),
    (103, 'David');
