import { useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

interface NavLeaf {
  to: string
  label: string
}

interface NavGroup {
  label: string
  items: NavLeaf[]
}

type NavEntry = NavLeaf | NavGroup

function isGroup(entry: NavEntry): entry is NavGroup {
  return 'items' in entry
}

// This branch surfaces only the What-If Studio group — the Soft Sensor
// Module's pages are still reachable via the routes in routes.tsx (they're
// not deleted, just no longer given their own flat sidebar entries here:
// Connect Data / Data Health / AI Feature Discovery / Build Model /
// Experiment History are reused as horizontal tabs inside What-If Setup's
// "Model Config" section instead — see ModelConfigTab.tsx).
const NAV_ENTRIES: NavEntry[] = [
  { to: '/', label: 'Overview' },
  {
    label: 'What-If Studio',
    items: [
      { to: '/what-if/overview', label: 'Welcome' },
      { to: '/what-if/case-setup', label: 'What-If Setup' },
      { to: '/what-if/dashboard', label: 'What-If Analysis' },
    ],
  },
]

function NavItem({ item }: { item: NavLeaf }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        padding: '0.5rem 0.6rem',
        borderRadius: 8,
        textDecoration: 'none',
        background: isActive ? 'var(--info-bg)' : 'transparent',
        transition: 'background 0.15s ease',
      })}
    >
      {({ isActive }) => (
        <span
          style={{
            color: isActive ? 'var(--accent)' : 'var(--text-caption)',
            fontWeight: isActive ? 700 : 500,
            fontSize: '0.87rem',
          }}
        >
          {item.label}
        </span>
      )}
    </NavLink>
  )
}

export function Sidebar() {
  const location = useLocation()
  const navRef = useRef<HTMLElement>(null)

  // The sidebar scrolls internally on shorter viewports (see the aside's
  // overflowY:auto below); on navigation, bring the newly-active item into
  // view within that scroll area instead of leaving the user to find it —
  // NavLink already marks the active link with aria-current="page".
  useEffect(() => {
    const activeLink = navRef.current?.querySelector('a[aria-current="page"]')
    activeLink?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [location.pathname])

  return (
    <aside
      style={{
        width: 248,
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        height: '100vh',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg-page)',
        borderRight: '1px solid var(--border)',
        padding: '1.25rem 1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', marginBottom: '1.5rem', padding: '0.25rem 0.25rem 0.9rem', borderBottom: '1px solid var(--border)' }}>
        <div
          style={{
            width: 36,
            height: 36,
            flexShrink: 0,
            borderRadius: 8,
            background: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
            <path
              d="M3 12h4l2-7 4 14 2-7h6"
              stroke="white"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <div
            style={{
              fontWeight: 700,
              fontSize: '1rem',
              color: 'var(--text-main)',
              lineHeight: 1.15,
              letterSpacing: '-0.01em',
            }}
          >
            SoftSense AI
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-caption)', marginTop: '0.1rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Industrial Intelligence
          </div>
        </div>
      </div>
      <nav ref={navRef} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        {NAV_ENTRIES.map((entry) =>
          isGroup(entry) ? (
            <div key={entry.label} style={{ marginTop: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              <div
                style={{
                  fontSize: '0.92rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--accent)',
                  padding: '0 0.6rem',
                  marginBottom: '0.3rem',
                }}
              >
                {entry.label}
              </div>
              {entry.items.map((item) => (
                <NavItem key={item.to} item={item} />
              ))}
            </div>
          ) : (
            <NavItem key={entry.to} item={entry} />
          ),
        )}
      </nav>
      <div style={{ flex: 1 }} />
      <div
        style={{
          borderTop: '1px solid var(--border)',
          paddingTop: '0.85rem',
          fontSize: '0.7rem',
          color: 'var(--text-faint)',
        }}
      >
        v1.0 · FastAPI · React
      </div>
    </aside>
  )
}
