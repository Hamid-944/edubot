import { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { ChevronDown, Sparkles, User } from 'lucide-react'
import { Message } from '../types'
import SourceCard from './SourceCard'

function TypingDots() {
  return (
    <span className="inline-flex items-end gap-[3px] h-4 ml-1">
      {[0, 1, 2].map(i => (
        <motion.span
          key={i}
          className="w-1 h-1 rounded-full bg-indigo-400"
          animate={{ y: [0, -4, 0] }}
          transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </span>
  )
}

export default function ChatMessage({ msg }: { msg: Message }) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const isBot = msg.role === 'bot'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={`flex gap-3 ${isBot ? 'justify-start' : 'justify-end'}`}
    >
      {/* Avatar */}
      {isBot && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full glass-strong border border-indigo-500/30 flex items-center justify-center shadow-glow-indigo mt-0.5">
          <Sparkles size={14} className="text-indigo-400" />
        </div>
      )}

      <div className={`max-w-[78%] space-y-2 ${isBot ? '' : 'items-end flex flex-col'}`}>
        {/* Bubble */}
        <div
          className={
            isBot
              ? 'glass rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-white/85 leading-relaxed border border-white/8 shadow-lg'
              : 'px-4 py-3 rounded-2xl rounded-tr-sm text-sm text-white leading-relaxed shadow-lg'
          }
          style={
            !isBot
              ? { background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }
              : undefined
          }
        >
          {isBot ? (
            msg.streaming && msg.content === '' ? (
              <span className="text-white/40 italic text-xs flex items-center gap-1">
                Thinking <TypingDots />
              </span>
            ) : (
              <div className="prose-invert text-sm">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
                {msg.streaming && <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 align-middle animate-cursor-blink" />}
              </div>
            )
          ) : (
            <span>{msg.content}</span>
          )}
        </div>

        {/* Sources toggle */}
        {isBot && !msg.streaming && msg.sources && msg.sources.length > 0 && (
          <div className="w-full space-y-2">
            <button
              onClick={() => setSourcesOpen(o => !o)}
              className="flex items-center gap-1.5 text-[11px] text-white/35 hover:text-white/60 transition-colors group"
            >
              <motion.div animate={{ rotate: sourcesOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown size={12} />
              </motion.div>
              {sourcesOpen ? 'Hide' : 'Show'} {msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}
              <span className="opacity-0 group-hover:opacity-100 transition-opacity text-indigo-400">
                · Pinecone + Cohere reranked
              </span>
            </button>

            {sourcesOpen && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-2"
              >
                {msg.sources.map((s, i) => (
                  <SourceCard key={i} source={s} rank={i + 1} />
                ))}
              </motion.div>
            )}
          </div>
        )}
      </div>

      {/* User avatar */}
      {!isBot && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full glass-strong border border-violet-500/30 flex items-center justify-center mt-0.5">
          <User size={14} className="text-violet-400" />
        </div>
      )}
    </motion.div>
  )
}
