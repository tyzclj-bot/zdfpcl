
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

// 你的 Lemon Squeezy Webhook Secret (需要在 Supabase 后台设置环境变量)
const WEBHOOK_SECRET = Deno.env.get('LEMON_SQUEEZY_WEBHOOK_SECRET')

serve(async (req) => {
  try {
    // 1. 验证请求方法
    if (req.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 })
    }

    // 2. 获取签名和原始 Body
    const signature = req.headers.get('x-signature') || ''
    const rawBody = await req.text()
    
    // 3. 验证签名 (HMAC SHA256)
    if (WEBHOOK_SECRET) {
        const isValid = await verifySignature(WEBHOOK_SECRET, signature, rawBody)
        if (!isValid) {
            return new Response('Invalid Signature', { status: 401 })
        }
    } else {
        console.warn("⚠️ Warning: LEMON_SQUEEZY_WEBHOOK_SECRET is not set. Skipping signature validation.")
    }

    // 4. 解析数据
    const payload = JSON.parse(rawBody)
    const eventName = payload.meta.event_name
    const customData = payload.meta.custom_data
    
    console.log(`Received event: ${eventName}`)

    // 5. 处理 "order_created" 事件 (支付成功)
    if (eventName === 'order_created') {
        const userId = customData?.user_id
        
        if (!userId) {
            console.error('No user_id found in custom_data')
            return new Response('No user_id provided', { status: 400 })
        }

        // 6. 初始化 Supabase Admin Client (用于绕过 RLS 写入数据)
        // 这些变量由 Supabase 平台自动注入
        const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
        const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
        
        const supabase = createClient(supabaseUrl, supabaseServiceKey)

        // 7. 更新用户状态
        // 假设我们给 Pro 用户增加 100 次额度，并标记为 'pro'
        const { error } = await supabase
            .from('user_credits')
            .update({ 
                plan_status: 'pro',
                credits_remaining: 100 // 或者你可以选择累加: credits_remaining + 100
            })
            .eq('user_id', userId)

        if (error) {
            console.error('Database update failed:', error)
            return new Response('Database update failed', { status: 500 })
        }

        console.log(`Successfully upgraded user ${userId} to Pro`)
    }

    return new Response(JSON.stringify({ received: true }), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })

  } catch (err) {
    console.error(err)
    return new Response(JSON.stringify({ error: err.message }), {
      headers: { "Content-Type": "application/json" },
      status: 400,
    })
  }
})

// 辅助函数：验证 Lemon Squeezy 签名
async function verifySignature(secret: string, signature: string, body: string): Promise<boolean> {
  const encoder = new TextEncoder()
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify']
  )
  
  // Convert hex signature to Uint8Array
  const signatureBytes = new Uint8Array(
    signature.match(/.{1,2}/g)!.map((byte) => parseInt(byte, 16))
  )

  return await crypto.subtle.verify(
    'HMAC',
    key,
    signatureBytes,
    encoder.encode(body)
  )
}
