export function createRuntimePage(ctx) {
  const { h, ref, onMounted } = ctx.vue

  return {
    name: 'RuntimeLotteryPage',
    setup() {
      const participantsText = ref('ChatGPT\nClaude\nGemini\nDeepSeek')
      const winnerCount = ref(1)
      const loading = ref(false)
      const meta = ref(null)
      const result = ref(null)
      const error = ref('')

      const fetchMeta = async () => {
        loading.value = true
        error.value = ''
        try {
          meta.value = await ctx.runtime.execute('/meta')
        } catch (err) {
          error.value = err instanceof Error ? err.message : '读取模块信息失败'
        } finally {
          loading.value = false
        }
      }

      const runDraw = async () => {
        const participants = participantsText.value
          .split(/\r?\n/)
          .map((item) => item.trim())
          .filter(Boolean)
        if (!participants.length) {
          ctx.runtime.notify.warning('请先输入参与人')
          return
        }

        loading.value = true
        error.value = ''
        try {
          result.value = await ctx.runtime.execute('/draw', {
            method: 'POST',
            body: {
              participants,
              winner_count: Number(winnerCount.value || 1)
            }
          })
          ctx.runtime.notify.success('抽奖完成')
        } catch (err) {
          error.value = err instanceof Error ? err.message : '抽奖失败'
        } finally {
          loading.value = false
        }
      }

      onMounted(fetchMeta)

      return () =>
        h('div', { style: pageStyle }, [
          h('div', { style: headerStyle }, [
            h('div', { style: badgeStyle }, 'Hot Plug Module'),
            h('h2', { style: titleStyle }, meta.value?.title || '抽奖模块演示'),
            h(
              'p',
              { style: subtitleStyle },
              '这个页面来自运行时模块包，加载后会立即出现在菜单和路由里。'
            )
          ]),
          h('div', { style: gridStyle }, [
            h('section', { style: cardStyle }, [
              h('label', { style: labelStyle }, '参与人'),
              h('textarea', {
                value: participantsText.value,
                rows: 10,
                style: textareaStyle,
                onInput: (event) => {
                  participantsText.value = event.target.value
                }
              }),
              h('div', { style: controlsStyle }, [
                h('input', {
                  type: 'number',
                  min: 1,
                  value: winnerCount.value,
                  style: inputStyle,
                  onInput: (event) => {
                    winnerCount.value = event.target.value
                  }
                }),
                h(
                  'button',
                  {
                    type: 'button',
                    disabled: loading.value,
                    style: buttonStyle,
                    onClick: runDraw
                  },
                  loading.value ? '执行中...' : '开始抽奖'
                )
              ])
            ]),
            h('section', { style: cardStyle }, [
              h('label', { style: labelStyle }, '结果'),
              h(
                'pre',
                { style: resultStyle },
                JSON.stringify(result.value || meta.value || { tip: '等待执行抽奖' }, null, 2)
              ),
              error.value ? h('p', { style: errorStyle }, error.value) : null
            ])
          ])
        ])
    }
  }
}

const pageStyle =
  'padding:24px;min-height:100%;background:linear-gradient(135deg,#fff7ed 0%,#fffbeb 100%);'
const headerStyle = 'display:flex;flex-direction:column;gap:10px;margin-bottom:20px;'
const badgeStyle =
  'display:inline-flex;align-items:center;width:max-content;padding:4px 10px;border-radius:999px;background:#fdba74;color:#7c2d12;font-size:12px;font-weight:700;'
const titleStyle = 'margin:0;font-size:28px;color:#7c2d12;'
const subtitleStyle = 'margin:0;color:#9a3412;line-height:1.6;max-width:720px;'
const gridStyle = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;'
const cardStyle =
  'padding:20px;border-radius:20px;background:#ffffff;box-shadow:0 18px 40px rgba(124,45,18,0.08);display:flex;flex-direction:column;gap:14px;'
const labelStyle = 'font-size:14px;font-weight:700;color:#7c2d12;'
const textareaStyle =
  'width:100%;padding:12px 14px;border-radius:14px;border:1px solid #fed7aa;outline:none;resize:vertical;box-sizing:border-box;'
const controlsStyle = 'display:flex;gap:12px;align-items:center;'
const inputStyle =
  'width:100px;padding:10px 12px;border-radius:12px;border:1px solid #fdba74;outline:none;'
const buttonStyle =
  'padding:10px 16px;border:none;border-radius:12px;background:#ea580c;color:#fff;font-weight:700;cursor:pointer;'
const resultStyle =
  'margin:0;padding:16px;border-radius:14px;background:#1c1917;color:#fed7aa;min-height:240px;overflow:auto;'
const errorStyle = 'margin:0;color:#dc2626;font-size:13px;'
