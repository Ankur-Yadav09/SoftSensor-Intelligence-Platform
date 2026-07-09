import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

const STORAGE_KEY = 'softsense.whatIfGeneratedTags'

interface ActiveWhatIfContextValue {
  generatedTags: string[]
  setGeneratedTags: (tags: string[]) => void
}

const ActiveWhatIfContext = createContext<ActiveWhatIfContextValue | null>(null)

function readStored(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

export function ActiveWhatIfProvider({ children }: { children: ReactNode }) {
  const [generatedTags, setGeneratedTagsState] = useState<string[]>(readStored)

  function setGeneratedTags(tags: string[]) {
    setGeneratedTagsState(tags)
    if (tags.length) localStorage.setItem(STORAGE_KEY, JSON.stringify(tags))
    else localStorage.removeItem(STORAGE_KEY)
  }

  return (
    <ActiveWhatIfContext.Provider value={{ generatedTags, setGeneratedTags }}>
      {children}
    </ActiveWhatIfContext.Provider>
  )
}

// Carries the Plant Configuration Wizard's generated tag list from Case Setup
// into the Dashboard's tag-source resolution (there's no server-side session
// in this module — see backend/app/services/what_if_service.py).
export function useActiveWhatIf() {
  const ctx = useContext(ActiveWhatIfContext)
  if (!ctx) throw new Error('useActiveWhatIf must be used within ActiveWhatIfProvider')
  return ctx
}
