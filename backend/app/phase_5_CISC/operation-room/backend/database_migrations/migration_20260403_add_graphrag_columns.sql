-- Database Migration: Add GraphRAG Columns to correlation_runs
-- Date: April 3, 2026
-- Phase: 3 (Database Schema & Hybrid Persistence Alignment)
-- 
-- This migration adds 4 columns to store GraphRAG results durably in DuckDB
-- Backward compatible: Existing runs continue to function

-- Add GraphRAG-specific columns to correlation_runs table
ALTER TABLE correlation_runs ADD COLUMN graphrag_narrative TEXT DEFAULT NULL;
ALTER TABLE correlation_runs ADD COLUMN shortest_path_json JSON DEFAULT NULL;
ALTER TABLE correlation_runs ADD COLUMN graph_engine_used VARCHAR DEFAULT 'fallback';
ALTER TABLE correlation_runs ADD COLUMN last_computed_at TIMESTAMP DEFAULT NULL;

-- Add Neo4j graph reference (for future cross-store queries)
ALTER TABLE correlation_runs ADD COLUMN neo4j_graph_id VARCHAR DEFAULT NULL;

-- Create index for faster lookups by engine
CREATE INDEX IF NOT EXISTS idx_correlation_runs_engine ON correlation_runs(graph_engine_used);

-- Create index for timestamp-based queries
CREATE INDEX IF NOT EXISTS idx_correlation_runs_last_computed ON correlation_runs(last_computed_at DESC);

-- Verify columns were added
-- SELECT column_name, column_type FROM information_schema.columns 
-- WHERE table_name = 'correlation_runs' 
-- ORDER BY ordinal_position;
