CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role VARCHAR(16) NOT NULL DEFAULT 'citizen' CHECK (role IN ('citizen','admin')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS complaints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reference_id VARCHAR(32) NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title VARCHAR(120) NOT NULL,
  description TEXT NOT NULL,
  category VARCHAR(50) NOT NULL,
  locality VARCHAR(120) NOT NULL,
  landmark VARCHAR(200),
  status VARCHAR(20) NOT NULL DEFAULT 'Submitted' CHECK (status IN ('Submitted','Under Review','Assigned','In Progress','Resolved','Reopened')),
  department VARCHAR(120) NOT NULL DEFAULT 'Not confirmed',
  is_demo BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS complaints_user_created_idx ON complaints(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS complaints_status_idx ON complaints(status);
CREATE INDEX IF NOT EXISTS complaints_category_idx ON complaints(category);
CREATE INDEX IF NOT EXISTS complaints_locality_idx ON complaints(locality);
CREATE TABLE IF NOT EXISTS complaint_history (
  id BIGSERIAL PRIMARY KEY,
  complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
  status VARCHAR(20) NOT NULL CHECK (status IN ('Submitted','Under Review','Assigned','In Progress','Resolved','Reopened')),
  note VARCHAR(1000) NOT NULL,
  actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
  actor_role VARCHAR(16) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS history_complaint_created_idx ON complaint_history(complaint_id, created_at DESC);
CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
  actor_role VARCHAR(16) NOT NULL,
  complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
  action VARCHAR(120) NOT NULL,
  reason VARCHAR(1000),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_created_idx ON audit_events(created_at DESC);
CREATE TABLE IF NOT EXISTS notifications (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  complaint_id UUID REFERENCES complaints(id) ON DELETE CASCADE,
  title VARCHAR(160) NOT NULL,
  message VARCHAR(500) NOT NULL,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications(user_id, created_at DESC);