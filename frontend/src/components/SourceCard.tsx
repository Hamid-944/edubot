import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, FileText, Hash, BarChart2 } from 'lucide-react'
import { Source, getSubjectMeta } from '../types'
import clsx from 'clsx'

interface ScoreBarProps { label: string; value: number; color: string }
function ScoreBar({ label, value, color }: ScoreBarProps) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-white/40">{label}</span>
        <span className={clsx('font-mono font-semibold', color)}>{value.toFixed(4)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
        <motion.div
          className={clsx('h-full rounded-full', color.replace('text-', 'bg-'))}
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
        />
      </div>
    </div>
  )
}

export default function SourceCard({ source, rank }: { source: Source; rank: number }) {
  const [open, setOpen] = useState(false)
  const meta = getSubjectMeta(source.subject)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: rank * 0.1 }}
      className={clsx(
        'rounded-xl border overflow-hidden transition-shadow duration-300',
        'glass',
        meta.border,
        open && meta.glow,
      )}
    >
      {/* Header — always visible */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 p-3 hover:bg-white/5 transition-colors text-left"
      >
        {/* Rank badge */}
        <span className={clsx('flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold', meta.badge)}>
          {rank}
        </span>

        {/* Subject + file */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={clsx('text-xs font-semibold uppercase tracking-widest', meta.color)}>
              {source.subject}
            </span>
            <span className="text-white/30 text-xs">·</span>
            <span className="text-white/50 text-xs truncate">{source.source}</span>
          </div>
          <div className="flex gap-3 mt-0.5 text-[11px] text-white/30">
            <span className="flex items-center gap-1">
              <Hash size={10} /> chunk {source.chunk_index + 1}/{source.total_chunks}
            </span>
            <span className="flex items-center gap-1">
              <BarChart2 size={10} />
              P: {source.pinecone_score.toFixed(3)}
              {source.rerank_score != null && <> · C: {source.rerank_score.toFixed(3)}</>}
            </span>
          </div>
        </div>

        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={14} className="text-white/30" />
        </motion.div>
      </button>

      {/* Expanded detail */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-3 border-t border-white/5 pt-3">
              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                {[
                  ['File', source.source],
                  ['Type', source.file_type],
                  ['Size', `${source.file_size_kb} KB`],
                  ['Location', `chars ${source.char_start.toLocaleString()}–${source.char_end.toLocaleString()}`],
                  ['Chunk size', `${source.chunk_size} chars`],
                  ['Ingested', source.ingested_at.slice(0, 10)],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-start gap-1.5">
                    <span className="text-white/30 min-w-[52px]">{k}</span>
                    <span className="text-white/70 font-mono break-all">{v}</span>
                  </div>
                ))}
              </div>

              {/* Score bars */}
              <div className="space-y-2 pt-1">
                <ScoreBar label="Pinecone similarity" value={source.pinecone_score} color={meta.color} />
                {source.rerank_score != null && (
                  <ScoreBar label={`Cohere rerank  (#${source.rerank_rank})`} value={source.rerank_score} color="text-indigo-400" />
                )}
              </div>

              {/* Chunk text */}
              <div className="rounded-lg bg-white/[0.03] border border-white/5 p-2.5">
                <div className="flex items-center gap-1.5 mb-2 text-[11px] text-white/30">
                  <FileText size={10} /> Retrieved passage
                </div>
                <p className="text-[12px] text-white/60 leading-relaxed line-clamp-6">{source.text}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
