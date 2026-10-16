/*
  main.jsx — React Entry Point

  This is the first JavaScript file the browser runs.
  It finds the <div id="root"> in index.html and mounts
  the entire React application inside it.

  StrictMode is a development-only wrapper that helps catch
  common mistakes. It has no effect in production.
*/

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
