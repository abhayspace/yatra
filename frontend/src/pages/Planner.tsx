import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Layout from '../components/Layout'
import { apiFetch } from '../lib/api'
import { saveTrip } from '../lib/trips'

const SUGGESTIONS: string[] = [
  'Plan a 5-day trip from Delhi for 2 people under ₹50,000, focused on nature and food, with a relaxed itinerary.',
  'Weekend getaway from Mumbai for a couple, budget ₹15,000, beaches and seafood.',
  '7-day family trip to Kerala, 4 people, ₹80,000, moderate pace.',
]

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface Requirements {
  destination?: string | null
  origin?: string | null
  travelers?: number | null
  budget_total?: number | null
  [key: string]: unknown
}

interface ChatResponse {
  reply: string
  thread_id: string
  requirements?: Requirements | null
}

export default function Planner() {
  const [params] = useSearchParams()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(
    params.get('thread')
  )
  const [requirements, setRequirements] = useState<Requirements | null>(null)
  const [saved, setSaved] = useState(false)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  async function send(text?: string) {
    const message = (text ?? input).trim()
    if (!message || busy) return

    setInput('')
    setSaved(false)
    setMessages((m) => [...m, { role: 'user', content: message }])
    setBusy(true)

    try {
      const data = await apiFetch<ChatResponse>('/api/chat', {
        method: 'POST',
        body: { message, thread_id: threadId },
      })
      if (!threadId) setThreadId(data.thread_id)
      if (data.requirements) setRequirements(data.requirements)
      setMessages((m) => [...m, { role: 'assistant', content: data.reply }])
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `⚠️ ${(err as Error).message}` },
      ])
    } finally {
      setBusy(false)
    }
  }

  function saveCurrentTrip() {
    const lastPlan = [...messages].reverse().find((m) => m.role === 'assistant')
    if (!lastPlan) return

    const req = requirements ?? {}
    saveTrip({
      id: crypto.randomUUID(),
      trip_name: req.destination
        ? `${req.destination} trip`
        : lastPlan.content.slice(0, 40).replace(/[#*]/g, '').trim(),
      origin: req.origin ?? null,
      destination: req.destination ?? null,
      travelers: req.travelers ?? null,
      budget: req.budget_total ?? null,
      itinerary: lastPlan.content,
      thread_id: threadId,
    })
    setSaved(true)
  }

  return (
    <Layout>
      <div className="planner">
        <div className="chat-area">
          {messages.length === 0 && (
            <div className="chat-empty">
              <h2>Plan your trip</h2>
              <p className="muted">
                Tell me where, when, who and how much — I'll handle the rest.
              </p>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="suggestion"
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg msg-${m.role}`}>
              {m.role === 'assistant' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {m.content}
                </ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
          ))}

          {busy && (
            <div className="msg msg-assistant">
              <span className="typing">Yatra AI is planning…</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input-bar">
          {threadId && messages.length > 0 && (
            <button
              className="btn btn-ghost"
              onClick={saveCurrentTrip}
              disabled={saved || busy}
            >
              {saved ? '✓ Saved' : '💾 Save trip'}
            </button>
          )}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder="Describe your trip… (Enter to send)"
            rows={2}
          />
          <button
            className="btn btn-primary"
            onClick={() => send()}
            disabled={busy || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </Layout>
  )
}
