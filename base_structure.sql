CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    username TEXT,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE course_images (
    image_id SERIAL PRIMARY KEY,
    image BYTEA  
);

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_name TEXT NOT NULL,
    course_description TEXT,
    course_price DECIMAL(10, 2),
    image_id INTEGER, 
    FOREIGN KEY (image_id) REFERENCES course_images(image_id) ON DELETE SET NULL
);
