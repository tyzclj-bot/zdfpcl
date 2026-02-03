
-- Run this in Supabase SQL Editor to enable Admin features

create or replace function public.get_admin_stats()
returns json
language plpgsql
security definer
as $$
declare
  user_count int;
  invoice_count int;
  caller_email text;
begin
  -- Get the email of the user calling the function from the JWT
  select auth.jwt() ->> 'email' into caller_email;

  -- Security Check: Only allow specific admin email
  -- You can add more emails here if needed
  if caller_email <> 'tyzclj@gmail.com' then
    raise exception 'Access Denied: Admin privileges required. Your email: %', caller_email;
  end if;

  -- Get counts
  -- 1. Total Users (using user_credits as a proxy for registered users)
  select count(*) into user_count from public.user_credits;
  
  -- 2. Total Invoices Processed
  select count(*) into invoice_count from public.invoice_history;

  return json_build_object(
    'total_users', user_count,
    'total_invoices', invoice_count
  );
end;
$$;
