import { motion } from 'framer-motion'
import { BookOpen, Database, RefreshCw, Layers } from 'lucide-react'
import { IngestEntry, getSubjectMeta } from '../types'
import FileUpload from './FileUpload'
import clsx from 'clsx'

interface Props {
  sources: Record<string, IngestEntry>
  totalVectors: number
  onUploaded: () => void
  onRebuild: () => void
  rebuilding: boolean
}

export default function Sidebar({ sources, totalVectors, onUploaded, onRebuild, rebuilding }: Props) {
  const entries = Object.entries(sources)

  return (
    <aside className="flex flex-col w-64 flex-shrink-0 h-full glass-strong border-r border-white/8 p-4 gap-5 overflow-y-auto">
      {/* Logo */}
      <div className="flex items-center gap-3 pt-1">
        <div className="w-9 h-9 rounded-xl glass-strong border border-indigo-500/40 flex items-center justify-center shadow-glow-indigo flex-shrink-0">
          <BookOpen size={16} className="text-indigo-400" />
        </div>
        <div>
          <p className="text-sm font-bold text-gradient leading-none">EduBot</p>
          <p className="text-[10px] text-white/30 mt-0.5">RAG Study Assistant</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2">
        <Stat icon={<Database size={12} />} label="Vectors" value={totalVectors.toLocaleString()} />
        <Stat icon={<Layers size={12} />}   label="Sources"  value={entries.length.toString()} />
      </div>

      {/* Pipeline badge */}
      <div className="rounded-xl glass border border-indigo-500/20 p-3 space-y-1.5">
        <p className="text-[10px] text-white/30 uppercase tracking-widest font-semibold">Pipeline</p>
        {['OpenAI Embeddings', 'Pinecone Vector DB', 'Cohere Reranker', 'GPT-4o-mini'].map((s, i) => (
          <div key={s} className="flex items-center gap-2 text-xs text-white/60">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400/60 flex-shrink-0" />
            <span>{s}</span>
            {i === 0 && <span className="ml-auto text-[10px] text-indigo-400/60">3-small</span>}
          </div>
        ))}
      </div>

      {/* Source list */}
      <div className="flex-1 space-y-2">
        <p className="text-[10px] text-white/30 uppercase tracking-widest font-semibold">Knowledge Base</p>
        {entries.length === 0 && (
          <p className="text-xs text-white/25 italic">No documents ingested yet</p>
        )}
        {entries.map(([file, info], i) => {
          const meta = getSubjectMeta(info.subject)
          return (
            <motion.div
              key={file}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className={clsx('rounded-lg glass border p-2.5 space-y-1', meta.border)}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs text-white/70 truncate leading-tight">{file}</span>
                <span className={clsx('text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0', meta.badge)}>
                  {info.file_type}
                </span>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-white/35">
                <span className={clsx('font-medium', meta.color)}>{info.subject}</span>
                <span>{info.total_chunks} chunks</span>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Upload */}
      <div className="space-y-2">
        <p className="text-[10px] text-white/30 uppercase tracking-widest font-semibold">Add Document</p>
        <FileUpload onUploaded={onUploaded} />
      </div>

      {/* Rebuild */}
      <button
        onClick={onRebuild}
        disabled={rebuilding}
        className="flex items-center justify-center gap-2 rounded-xl py-2 text-xs text-white/40 hover:text-white/70 glass border border-white/10 hover:border-red-500/30 hover:text-red-400 transition-all duration-200 disabled:opacity-50"
      >
        <RefreshCw size={12} className={rebuilding ? 'animate-spin' : ''} />
        {rebuilding ? 'Rebuilding...' : 'Rebuild from scratch'}
      </button>
    </aside>
  )
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="glass rounded-xl border border-white/8 px-3 py-2.5 space-y-1">
      <div className="flex items-center gap-1.5 text-[10px] text-white/30">
        {icon} {label}
      </div>
      <p className="text-lg font-bold text-white/90 leading-none">{value}</p>
    </div>
  )
}
