-- Add license_key column to user_credits for Gumroad Pro 秘钥绑定
-- 在 Supabase Dashboard 的 SQL Editor 中运行此脚本

alter table public.user_credits 
add column if not exists license_key text;
