CREATE DATABASE sensor_db; 
USE sensor_db; 
CREATE TABLE sensor_data ( 
id INT AUTO_INCREMENT PRIMARY KEY, 
sensor_type VARCHAR(50), 
value FLOAT, 
timestamp DATETIME 
); 