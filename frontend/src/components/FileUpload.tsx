import { useRef, useState, DragEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface Props {
  onUploaded: () => void
}

type UploadState = 'idle' | 'dragging' | 'uploading' | 'success' | 'error'

export default function FileUpload({ onUploaded }: Props) {
  const [state, setState] = useState<UploadState>('idle')
  const [message, setMessage] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = async (file: File) => {
    setState('uploading')
    setMessage(`Uploading ${file.name}...`)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch('/api/ingest', { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      setState('success')
      setMessage(`+${data.added} chunks from ${data.filename}`)
      onUploaded()
      setTimeout(() => { setState('idle'); setMessage('') }, 3000)
    } catch (e: unknown) {
      setState('error')
      setMessage(e instanceof Error ? e.message : 'Upload failed')
      setTimeout(() => { setState('idle'); setMessage('') }, 3000)
    }
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setState('idle')
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  const icon = {
    idle:      <UploadCloud size={18} className="text-white/30" />,
    dragging:  <UploadCloud size={18} className="text-indigo-400 animate-bounce" />,
    uploading: <Loader2 size={18} className="text-indigo-400 animate-spin" />,
    success:   <CheckCircle size={18} className="text-emerald-400" />,
    error:     <XCircle size={18} className="text-red-400" />,
  }[state]

  const borderColor = {
    idle:      'border-white/10 hover:border-indigo-500/40',
    dragging:  'border-indigo-500/70',
    uploading: 'border-indigo-500/40',
    success:   'border-emerald-500/50',
    error:     'border-red-500/50',
  }[state]

  return (
    <div
      onDragOver={e => { e.preventDefault(); setState('dragging') }}
      onDragLeave={() => setState('idle')}
      onDrop={onDrop}
      onClick={() => state === 'idle' && inputRef.current?.click()}
      className={`relative rounded-xl border-2 border-dashed p-3 transition-all duration-200 cursor-pointer group ${borderColor}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.pdf"
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = '' }}
      />

      <AnimatePresence mode="wait">
        <motion.div
          key={state}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className="flex items-center gap-2"
        >
          {icon}
          <span className={`text-xs truncate ${
            state === 'success' ? 'text-emerald-400' :
            state === 'error'   ? 'text-red-400' :
            state === 'dragging'? 'text-indigo-300' :
            'text-white/30 group-hover:text-white/50'
          }`}>
            {message || 'Drop .txt / .pdf or click to upload'}
          </span>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
