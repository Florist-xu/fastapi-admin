export function createRuntimePage(ctx) {
  const { h, ref, onMounted } = ctx.vue

  return {
    name: 'RuntimeFlashSalePage',
    setup() {
      const loading = ref(false)
      const buyer = ref('演示用户A')
      const quantity = ref(1)
      const state = ref(null)
      const result = ref(null)
      const error = ref('')

      const createStat = (label, value) =>
        h('div', { style: statItemStyle }, [
          h('span', { style: statLabelStyle }, label),
          h('strong', { style: statValueStyle }, value)
        ])

      const fetchState = async () => {
        loading.value = true
        error.value = ''
        try {
          state.value = await ctx.runtime.execute('/state')
        } catch (err) {
          error.value = err instanceof Error ? err.message : '读取秒杀状态失败'
        } finally {
          loading.value = false
        }
      }

      const purchase = async () => {
        loading.value = true
        error.value = ''
        try {
          result.value = await ctx.runtime.execute('/purchase', {
            method: 'POST',
            body: {
              buyer: buyer.value,
              quantity: Number(quantity.value || 1)
            }
          })
          await fetchState()
        } catch (err) {
          error.value = err instanceof Error ? err.message : '抢购失败'
        } finally {
          loading.value = false
        }
      }

      const resetState = async () => {
        loading.value = true
        error.value = ''
        try {
          await ctx.runtime.execute('/reset', { method: 'POST', body: {} })
          result.value = null
          ctx.runtime.notify.success('秒杀场景已重置')
          await fetchState()
        } catch (err) {
          error.value = err instanceof Error ? err.message : '重置失败'
        } finally {
          loading.value = false
        }
      }

      onMounted(fetchState)

      return () =>
        h('div', { style: shellStyle }, [
          h('div', { style: heroStyle }, [
            h('div', { style: badgeFlashStyle }, 'Runtime Commerce'),
            h('h2', { style: flashTitleStyle }, state.value?.title || '秒杀模块演示'),
            h(
              'p',
              { style: flashSubtitleStyle },
              state.value?.subtitle || '页面和业务接口都来自运行时模块，无需重新打包前端。'
            )
          ]),
          h('div', { style: flashGridStyle }, [
            h('section', { style: flashCardStyle }, [
              h('div', { style: statGridStyle }, [
                createStat('状态', state.value?.status || '--'),
                createStat('库存', String(state.value?.remaining_stock ?? '--')),
                createStat('价格', `￥${state.value?.sale_price ?? '--'}`),
                createStat('倒计时', String(state.value?.countdown_text || '--'))
              ]),
              h('div', { style: formRowStyle }, [
                h('input', {
                  value: buyer.value,
                  placeholder: '购买人',
                  style: inputStyle,
                  onInput: (event) => {
                    buyer.value = event.target.value
                  }
                }),
                h('input', {
                  type: 'number',
                  min: 1,
                  value: quantity.value,
                  style: inputStyle,
                  onInput: (event) => {
                    quantity.value = event.target.value
                  }
                })
              ]),
              h('div', { style: controlsStyle }, [
                h(
                  'button',
                  {
                    type: 'button',
                    disabled: loading.value,
                    style: buttonPrimaryStyle,
                    onClick: purchase
                  },
                  loading.value ? '提交中...' : '立即抢购'
                ),
                h(
                  'button',
                  {
                    type: 'button',
                    disabled: loading.value,
                    style: buttonGhostStyle,
                    onClick: fetchState
                  },
                  '刷新状态'
                ),
                h(
                  'button',
                  {
                    type: 'button',
                    disabled: loading.value,
                    style: buttonGhostStyle,
                    onClick: resetState
                  },
                  '重置'
                )
              ])
            ]),
            h('section', { style: flashCardStyle }, [
              h('label', { style: labelStyle }, '结果'),
              h(
                'pre',
                { style: resultStyle },
                JSON.stringify(result.value || state.value || { tip: '等待读取状态' }, null, 2)
              ),
              error.value ? h('p', { style: errorStyle }, error.value) : null
            ])
          ])
        ])
    }
  }
}

const shellStyle =
  'padding:24px;min-height:100%;background:linear-gradient(140deg,#eff6ff 0%,#ecfeff 100%);'
const heroStyle = 'display:flex;flex-direction:column;gap:10px;margin-bottom:20px;'
const badgeFlashStyle =
  'display:inline-flex;align-items:center;width:max-content;padding:4px 10px;border-radius:999px;background:#93c5fd;color:#1d4ed8;font-size:12px;font-weight:700;'
const flashTitleStyle = 'margin:0;font-size:28px;color:#0f172a;'
const flashSubtitleStyle = 'margin:0;color:#0f766e;line-height:1.6;max-width:760px;'
const flashGridStyle = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;'
const flashCardStyle =
  'padding:20px;border-radius:20px;background:#ffffff;box-shadow:0 18px 40px rgba(15,23,42,0.08);display:flex;flex-direction:column;gap:14px;'
const statGridStyle = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;'
const statItemStyle = 'padding:14px;border-radius:16px;background:#eff6ff;display:flex;flex-direction:column;gap:6px;'
const statLabelStyle = 'font-size:12px;color:#475569;'
const statValueStyle = 'font-size:18px;color:#0f172a;'
const formRowStyle = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;'
const controlsStyle = 'display:flex;gap:12px;flex-wrap:wrap;'
const buttonPrimaryStyle =
  'padding:10px 16px;border:none;border-radius:12px;background:#0284c7;color:#fff;font-weight:700;cursor:pointer;'
const buttonGhostStyle =
  'padding:10px 16px;border:1px solid #bae6fd;border-radius:12px;background:#fff;color:#0369a1;font-weight:700;cursor:pointer;'
const inputStyle =
  'width:100%;padding:10px 12px;border-radius:12px;border:1px solid #bae6fd;outline:none;box-sizing:border-box;'
const labelStyle = 'font-size:14px;font-weight:700;color:#0f172a;'
const resultStyle =
  'margin:0;padding:16px;border-radius:14px;background:#0f172a;color:#bfdbfe;min-height:260px;overflow:auto;'
const errorStyle = 'margin:0;color:#dc2626;font-size:13px;'
