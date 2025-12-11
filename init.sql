-- Initialize database for Gemini Agent
-- Run this connected to 'postgres' database first to create the gemini database

-- Create database (run this first, connected to 'postgres')
-- CREATE DATABASE gemini;

-- Then connect to 'gemini' database and run the rest:

-- Chat history table (compatible with n8n format)
CREATE TABLE IF NOT EXISTS n8n_chat_histories_geminiv2 (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast session lookups
CREATE INDEX IF NOT EXISTS idx_chat_session_created 
ON n8n_chat_histories_geminiv2(session_id, created_at DESC);

-- Logs table for tracking user requests
CREATE TABLE IF NOT EXISTS logsgemini (
    userid VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    correo VARCHAR(255) NOT NULL,
    peticiones INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for auto-updating timestamp
DROP TRIGGER IF EXISTS update_logsgemini_updated_at ON logsgemini;
CREATE TRIGGER update_logsgemini_updated_at
    BEFORE UPDATE ON logsgemini
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Cleanup old chat history (optional, run periodically)
-- DELETE FROM n8n_chat_histories_geminiv2 WHERE created_at < NOW() - INTERVAL '30 days';
