create database date-a-wolfie;

use sbu_dating;

CREATE TABLE Users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    major VARCHAR(255),
    clubs TEXT,
    bio TEXT,
    looking_for ENUM('Dating', 'Long-term Relationship', 'Friendship', 'Casual Relationship') NOT NULL,
    sexual_orientation ENUM('Straight', 'Gay', 'Lesbian', 'Bisexual') NOT NULL,
    interests TEXT
);

CREATE TABLE Messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    message TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (sender_id) REFERENCES Users(id),
    FOREIGN KEY (receiver_id) REFERENCES Users(id)
);

CREATE TABLE Interested_Requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (sender_id) REFERENCES Users(id),
    FOREIGN KEY (receiver_id) REFERENCES Users(id)
);

CREATE TABLE Sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    session_id VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id)
);


CREATE TABLE Profile_Pictures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    filename VARCHAR(255),
    uploaded_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id)
);


SELECT * FROM messages;
