(function () {
  var script = document.currentScript
  if (!script) return

  var endpoint = script.getAttribute('data-endpoint')
  if (!endpoint) return

  var assetOrigin = new URL(script.src, window.location.href).origin
  var title = script.getAttribute('data-title') || 'Chat'
  var root = document.createElement('div')
  var button = document.createElement('button')
  var frame = document.createElement('iframe')
  var open = false

  root.style.position = 'fixed'
  root.style.right = '20px'
  root.style.bottom = '20px'
  root.style.zIndex = '2147483000'
  root.style.fontFamily = 'system-ui, sans-serif'

  frame.title = title
  frame.src =
    assetOrigin +
    '/widget.html?endpoint=' +
    encodeURIComponent(endpoint) +
    '&title=' +
    encodeURIComponent(title)
  frame.style.display = 'none'
  frame.style.width = 'min(380px, calc(100vw - 32px))'
  frame.style.height = 'min(560px, calc(100vh - 96px))'
  frame.style.marginBottom = '12px'
  frame.style.border = '0'
  frame.style.borderRadius = '16px'
  frame.style.boxShadow = '0 20px 60px rgba(0, 0, 0, 0.28)'
  frame.style.background = '#ffffff'

  button.type = 'button'
  button.textContent = title
  button.setAttribute('aria-expanded', 'false')
  button.style.display = 'block'
  button.style.marginLeft = 'auto'
  button.style.padding = '12px 18px'
  button.style.border = '0'
  button.style.borderRadius = '999px'
  button.style.background = '#171717'
  button.style.color = '#ffffff'
  button.style.font = '600 14px system-ui, sans-serif'
  button.style.cursor = 'pointer'
  button.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.22)'

  button.addEventListener('click', function () {
    open = !open
    frame.style.display = open ? 'block' : 'none'
    button.textContent = open ? 'Close' : title
    button.setAttribute('aria-expanded', String(open))
  })

  root.appendChild(frame)
  root.appendChild(button)
  document.body.appendChild(root)
})()
