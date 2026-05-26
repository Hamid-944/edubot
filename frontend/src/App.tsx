import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Sparkles, BookOpen, Zap } from 'lucide-react'
import { Message, IngestEntry, Source } from './types'
import Background from './components/Background'
import Sidebar from './components/Sidebar'
import ChatMessage from './components/ChatMessage'

const WELCOME_PROMPTS = [
  'What is photosynthesis?',
  'How do I solve a linear equation?',
  'What are the parts of speech?',
  'Name the continents of the world',
]

export default function App() {
  const [messages, setMessages]         = useState<Message[]>([])
  const [input, setInput]               = useState('')
  const [streaming, setStreaming]       = useState(false)
  const [sources, setSources]           = useState<Record<string, IngestEntry>>({})
  const [totalVectors, setTotalVectors] = useState(0)
  const [rebuilding, setRebuilding]     = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)

  const refreshStatus = useCallback(async () => {
    try {
      const [statusRes, sourcesRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/sources'),
      ])
      const status  = await statusRes.json()
      const sources = await sourcesRes.json()
      setTotalVectors(status.total_vectors ?? 0)
      setSources(sources)
    } catch { /* server not up yet */ }
  }, [])

  useEffect(() => { refreshStatus() }, [refreshStatus])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const sendMessage = async (question: string) => {
    if (!question.trim() || streaming) return
    setInput('')

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: question }
    const botId = (Date.now() + 1).toString()
    const botMsg: Message  = { id: botId, role: 'bot', content: '', streaming: true }
    setMessages(prev => [...prev, userMsg, botMsg])
    setStreaming(true)

    let accText  = ''
    let chunks: Source[] = []

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      const reader  = res.body!.getReader()
      const decoder = new TextDecoder()
      let   buf     = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'chunks') {
              chunks = evt.data as Source[]
            } else if (evt.type === 'token') {
              accText += evt.data
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, content: accText, sources: chunks } : m
              ))
            } else if (evt.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, streaming: false, sources: chunks } : m
              ))
            } else if (evt.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, content: `Error: ${evt.data}`, streaming: false } : m
              ))
            }
          } catch { /* malformed line */ }
        }
      }
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === botId
          ? { ...m, content: 'Connection error. Is the API server running?', streaming: false }
          : m
      ))
    } finally {
      setStreaming(false)
    }
  }

  const handleRebuild = async () => {
    setRebuilding(true)
    try { await fetch('/api/rebuild', { method: 'POST' }) } catch { /* ignore */ }
    await refreshStatus()
    setRebuilding(false)
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Background />
      <Sidebar
        sources={sources}
        totalVectors={totalVectors}
        onUploaded={refreshStatus}
        onRebuild={handleRebuild}
        rebuilding={rebuilding}
      />

      {/* Main chat area */}
      <main className="flex flex-col flex-1 min-w-0 h-full">
        {/* Header */}
        <header className="flex-shrink-0 flex items-center justify-between px-6 py-4 glass-strong border-b border-white/8">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(52,211,153,0.5)] animate-pulse-glow" />
            <span className="text-sm font-semibold text-white/70">EduBot is ready</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-white/30">
            <Zap size={10} className="text-amber-400" />
            Pinecone + Cohere + GPT-4o-mini
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          <AnimatePresence initial={false}>
            {messages.length === 0 && (
              <motion.div
                key="welcome"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="flex flex-col items-center justify-center h-full text-center pt-16 space-y-8"
              >
                {/* Hero icon */}
                <motion.div
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
                  className="w-20 h-20 rounded-3xl glass-strong border border-indigo-500/40 flex items-center justify-center shadow-glow-indigo"
                >
                  <BookOpen size={36} className="text-indigo-400" />
                </motion.div>

                <div className="space-y-2">
                  <h1 className="text-3xl font-bold shimmer-text">Ask EduBot</h1>
                  <p className="text-white/35 text-sm max-w-sm">
                    Your AI study assistant for Mathematics, Science, English & Social Studies
                  </p>
                </div>

                {/* Suggestion chips */}
                <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                  {WELCOME_PROMPTS.map(p => (
                    <button
                      key={p}
                      onClick={() => sendMessage(p)}
                      className="px-4 py-2 rounded-full text-xs glass border border-white/10 hover:border-indigo-500/40 text-white/50 hover:text-white/80 hover:shadow-glow-indigo transition-all duration-200"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {messages.map(msg => (
              <ChatMessage key={msg.id} msg={msg} />
            ))}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex-shrink-0 px-6 py-4 glass-strong border-t border-white/8">
          <div className={`flex items-end gap-3 rounded-2xl glass border p-3 transition-all duration-300 ${
            streaming ? 'border-indigo-500/30' : 'border-white/10 focus-within:border-indigo-500/50 focus-within:shadow-glow-indigo'
          }`}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
              rows={1}
              disabled={streaming}
              className="flex-1 bg-transparent text-sm text-white/85 placeholder-white/25 resize-none outline-none max-h-32 overflow-y-auto leading-relaxed disabled:opacity-50"
              style={{ height: 'auto', minHeight: '24px' }}
              onInput={e => {
                const t = e.currentTarget
                t.style.height = 'auto'
                t.style.height = Math.min(t.scrollHeight, 128) + 'px'
              }}
            />
            <motion.button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || streaming}
              whileTap={{ scale: 0.9 }}
              whileHover={{ scale: 1.05 }}
              className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-200 disabled:opacity-30"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              {streaming
                ? <Sparkles size={16} className="text-white animate-spin-slow" />
                : <Send size={15} className="text-white" />
              }
            </motion.button>
          </div>
          <p className="text-[10px] text-white/20 mt-2 text-center">
            Answers grounded in your study materials via RAG · Pinecone retrieval · Cohere reranking
          </p>
        </div>
      </main>
    </div>
  )
}
