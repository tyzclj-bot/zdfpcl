-- Add plan_status column to user_credits table
alter table public.user_credits 
add column if not exists plan_status text default 'free';
