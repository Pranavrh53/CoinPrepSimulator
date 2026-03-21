-- Add risk_score column if it doesn't exist
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS risk_score INT DEFAULT 0;

-- Update risk_tolerance column to support longer values
ALTER TABLE users 
MODIFY COLUMN risk_tolerance VARCHAR(50) DEFAULT 'Medium';

-- Verify the changes
DESCRIBE users;
