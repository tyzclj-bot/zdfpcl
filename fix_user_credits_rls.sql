-- ============================================================
-- user_credits 表 RLS 修复脚本
-- 在 Supabase Dashboard → SQL Editor 中运行
-- ============================================================
-- 问题：缺少 INSERT 策略，导致 save_license_key 等操作触发 403
-- 解决：为 authenticated 用户添加 INSERT 策略，并完善 UPDATE 的 WITH CHECK
-- ============================================================

-- 1. 删除并重建 UPDATE 策略（补充 WITH CHECK）
DROP POLICY IF EXISTS "Users can update their own credits" ON public.user_credits;

CREATE POLICY "Users can update their own credits"
  ON public.user_credits FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- 2. 新增 INSERT 策略（原 setup 缺失，导致 403）
DROP POLICY IF EXISTS "Users can insert their own credits" ON public.user_credits;

CREATE POLICY "Users can insert their own credits"
  ON public.user_credits FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- 3. SELECT 策略应在初始 supabase_setup.sql 中已创建，无需重复
