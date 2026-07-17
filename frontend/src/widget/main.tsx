import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { WidgetApp } from './WidgetApp'
import './widget.css'

const params = new URLSearchParams(window.location.search)
const endpoint = params.get('endpoint') ?? ''
const title = params.get('title')?.trim() || 'Chat'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WidgetApp endpoint={endpoint} title={title} />
  </StrictMode>,
)
