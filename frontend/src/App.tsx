import { useEffect, useState } from 'react'
import './App.css'

type Health = {
  status: string
}

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: Health) => setHealth(data))
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <div className="card">
      <h1>Engineering Memory OS</h1>
      <p>Frontend: <strong>up</strong></p>
      <p>
        Backend:{' '}
        {error ? (
          <strong style={{ color: 'red' }}>error ({error})</strong>
        ) : health ? (
          <strong style={{ color: 'green' }}>{health.status}</strong>
        ) : (
          'checking…'
        )}
      </p>
    </div>
  )
}

export default App
