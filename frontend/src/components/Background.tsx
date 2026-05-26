export default function Background() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      {/* Base gradient */}
      <div className="absolute inset-0 bg-dark-950" />

      {/* Animated blobs */}
      <div
        className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full opacity-[0.12] animate-blob"
        style={{ background: 'radial-gradient(circle, #6366f1, #4f46e5, transparent 70%)' }}
      />
      <div
        className="absolute top-1/3 -right-32 w-[500px] h-[500px] rounded-full opacity-[0.10] animate-blob-slow"
        style={{ background: 'radial-gradient(circle, #8b5cf6, #7c3aed, transparent 70%)', animationDelay: '-5s' }}
      />
      <div
        className="absolute -bottom-32 left-1/3 w-[450px] h-[450px] rounded-full opacity-[0.08] animate-blob"
        style={{ background: 'radial-gradient(circle, #06b6d4, #0891b2, transparent 70%)', animationDelay: '-9s' }}
      />
      <div
        className="absolute top-1/2 left-1/2 w-[350px] h-[350px] rounded-full opacity-[0.06] animate-blob-slow"
        style={{ background: 'radial-gradient(circle, #a78bfa, transparent 70%)', animationDelay: '-3s' }}
      />

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: 'linear-gradient(rgba(99,102,241,1) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,1) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
        }}
      />
    </div>
  )
}
