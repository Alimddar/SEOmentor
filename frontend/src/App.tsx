import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import axios from 'axios'

type View = 'landing' | 'analyze' | 'loading' | 'dashboard' | 'history'

type CompetitorItem = {
  name: string
  reason: string
  url?: string
}

type RoadmapDay = {
  day: number
  task: string
}

type AnalyzeResponse = {
  project_id: number
}

type SendEmailResponse = {
  sent: boolean
  message: string
}

type DayDetailResponse = {
  day: number
  task: string
  description: string
  checklist: string[]
  kpi: string
}

type ProjectResponse = {
  seo_score: number
  issues: string[]
  competitors: CompetitorItem[]
  keyword_gaps: string[]
  roadmap: RoadmapDay[]
}

type HistoryItem = {
  id: number
  url: string
  seo_score: number
  plan_days: number
  created_at: string
}

type AnalyzeForm = {
  url: string
  country: string
  language: string
  plan_days: number
  primary_goal: string
  business_offer: string
  target_audience: string
  priority_pages: string
  seed_keywords: string
  known_competitors: string
  execution_capacity: string
}

type AnalyzePayload = {
  url: string
  country: string
  language: string
  plan_days: number
  primary_goal: string
  business_offer: string
  target_audience: string
  priority_pages: string[]
  seed_keywords: string[]
  known_competitors: string[]
  execution_capacity: string
}

type CalendarPlanItem = {
  date: Date
  task: string
  roadmapDay: number
}

type CalendarCell = {
  key: string
  isPlaceholder: boolean
  date?: Date
  task?: string
  roadmapDay?: number
  isInPlan?: boolean
  isToday?: boolean
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
})

const loadingSteps = ['Analyzing website...', 'Finding competitors...', 'Generating roadmap...']

const COUNTRY_OPTIONS = [
  'Azerbaijan',
  'United States',
  'United Kingdom',
  'Turkey',
  'Germany',
  'France',
  'Canada',
  'UAE',
  'Saudi Arabia',
  'India',
]

const LANGUAGE_OPTIONS = ['English', 'Azerbaijani', 'Turkish', 'Russian', 'German', 'French', 'Arabic']
const GOAL_OPTIONS = [
  'Increase organic traffic',
  'Generate qualified leads',
  'Increase online sales',
  'Improve brand visibility',
]
const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function normalizeUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function formatCreatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function hostnameLabel(rawUrl: string): string {
  try {
    const host = new URL(normalizeUrl(rawUrl)).hostname
    return host.replace(/^www\./, '')
  } catch {
    return rawUrl
  }
}

function parseListInput(raw: string): string[] {
  return raw
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 15)
}

function extractDomainCandidate(text: string): string {
  const source = String(text || '')
  const match =
    source.match(/https?:\/\/[^\s)]+/i) ||
    source.match(/\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s)]*)?/i)
  return match ? match[0].replace(/[),.;]+$/, '') : ''
}

function extractWoltCandidate(text: string): string {
  const source = String(text || '')
  const match = source.match(/https?:\/\/[^\s)]*wolt\.com[^\s)]*/i)
  return match ? match[0].replace(/[),.;]+$/, '') : ''
}

function competitorHref(item: CompetitorItem): string {
  const direct = String(item.url || '').trim()
  const directWolt = extractWoltCandidate(direct)
  if (directWolt) return directWolt
  if (/^https?:\/\//i.test(direct)) return direct
  if (direct) return `https://${direct.replace(/^\/+/, '')}`

  const reasonWolt = extractWoltCandidate(item.reason)
  if (reasonWolt) return reasonWolt
  const fromReason = extractDomainCandidate(item.reason)
  if (/^https?:\/\//i.test(fromReason)) return fromReason
  if (fromReason) return `https://${fromReason.replace(/^\/+/, '')}`

  const nameWolt = extractWoltCandidate(item.name)
  if (nameWolt) return nameWolt
  const fromName = extractDomainCandidate(item.name)
  if (/^https?:\/\//i.test(fromName)) return fromName
  if (fromName) return `https://${fromName.replace(/^\/+/, '')}`

  return `https://www.google.com/search?q=${encodeURIComponent(`site:wolt.com ${item.name}`)}`
}

function toDateKey(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function formatMonthYear(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

function formatShortDate(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function clearProjectIdFromUrl(): void {
  const url = new URL(window.location.href)
  if (!url.searchParams.has('project_id')) return
  url.searchParams.delete('project_id')
  const query = url.searchParams.toString()
  const next = `${url.pathname}${query ? `?${query}` : ''}${url.hash}`
  window.history.replaceState({}, '', next)
}

function App() {
  const [view, setView] = useState<View>('landing')
  const [form, setForm] = useState<AnalyzeForm>({
    url: '',
    country: 'Azerbaijan',
    language: 'English',
    plan_days: 30,
    primary_goal: 'Increase organic traffic',
    business_offer: '',
    target_audience: '',
    priority_pages: '',
    seed_keywords: '',
    known_competitors: '',
    execution_capacity: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [projectId, setProjectId] = useState<number | null>(null)
  const [result, setResult] = useState<ProjectResponse | null>(null)
  const [lastPlanDays, setLastPlanDays] = useState(30)
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false)
  const [emailInput, setEmailInput] = useState('')
  const [emailStatus, setEmailStatus] = useState<string | null>(null)
  const [isEmailSending, setIsEmailSending] = useState(false)
  const [isDayModalOpen, setIsDayModalOpen] = useState(false)
  const [dayDetailLoading, setDayDetailLoading] = useState(false)
  const [dayDetailError, setDayDetailError] = useState<string | null>(null)
  const [dayDetail, setDayDetail] = useState<DayDetailResponse | null>(null)
  const [selectedDayMeta, setSelectedDayMeta] = useState<{
    day: number
    dateLabel: string
    task: string
  } | null>(null)
  const [calendarMonthIndex, setCalendarMonthIndex] = useState(0)
  const [planStartDate] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), now.getDate())
  })

  useEffect(() => {
    const projectFromQuery = new URLSearchParams(window.location.search).get('project_id')
    if (!projectFromQuery) return
    const id = Number(projectFromQuery)
    if (Number.isNaN(id) || id < 1) return
    setProjectId(id)
    setView('dashboard')
    void fetchProject(id)
  }, [])

  useEffect(() => {
    if (view !== 'loading') return
    const timer = window.setInterval(() => {
      setLoadingStep((prev) => (prev + 1) % loadingSteps.length)
    }, 1400)
    return () => window.clearInterval(timer)
  }, [view])

  useEffect(() => {
    if (view === 'history') {
      void fetchHistory()
    }
  }, [view])

  async function fetchHistory() {
    setHistoryLoading(true)
    setError(null)
    try {
      const response = await api.get<HistoryItem[]>('/projects', { params: { limit: 40 } })
      setHistoryItems(response.data)
    } catch (err) {
      setError('Could not load project history.')
    } finally {
      setHistoryLoading(false)
    }
  }

  async function fetchProject(id: number) {
    setIsBusy(true)
    setError(null)
    try {
      const response = await api.get<ProjectResponse>(`/project/${id}`)
      setResult(response.data)
      setIsDayModalOpen(false)
      setDayDetail(null)
      setDayDetailError(null)
      setView('dashboard')
      window.history.replaceState({}, '', `/?project_id=${id}`)
    } catch (err) {
      setError('Could not load dashboard data. Please try again.')
      setView('analyze')
    } finally {
      setIsBusy(false)
    }
  }

  async function handleAnalyzeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    const normalizedUrl = normalizeUrl(form.url)
    if (!normalizedUrl) {
      setError('Website URL is required.')
      return
    }

    let parsedUrl: URL
    try {
      parsedUrl = new URL(normalizedUrl)
    } catch {
      setError('Please enter a valid website URL.')
      return
    }
    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      setError('URL must start with http:// or https://')
      return
    }

    if (form.plan_days < 7 || form.plan_days > 30) {
      setError('Roadmap length must be between 7 and 30 days.')
      return
    }

    const primaryGoal = form.primary_goal.trim()
    if (!primaryGoal) {
      setError('Primary goal is required.')
      return
    }

    const businessOffer = form.business_offer.trim()
    if (!businessOffer) {
      setError('Business type / offer is required.')
      return
    }

    const payload: AnalyzePayload = {
      url: parsedUrl.toString(),
      country: form.country,
      language: form.language,
      plan_days: form.plan_days,
      primary_goal: primaryGoal,
      business_offer: businessOffer,
      target_audience: form.target_audience.trim(),
      priority_pages: parseListInput(form.priority_pages),
      seed_keywords: parseListInput(form.seed_keywords),
      known_competitors: parseListInput(form.known_competitors),
      execution_capacity: form.execution_capacity.trim(),
    }

    setIsBusy(true)
    setView('loading')
    setLoadingStep(0)
    setResult(null)
    setLastPlanDays(form.plan_days)
    setForm((prev) => ({ ...prev, url: parsedUrl.toString() }))

    try {
      const analyzeResponse = await api.post<AnalyzeResponse>('/analyze', payload)
      const newProjectId = analyzeResponse.data.project_id
      setProjectId(newProjectId)
      await fetchProject(newProjectId)
    } catch (err) {
      setError('Analysis failed. Please verify URL and try again.')
      setView('analyze')
    } finally {
      setIsBusy(false)
    }
  }

  async function handleEmailSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setEmailStatus(null)

    if (!projectId) {
      setEmailStatus('Project is not loaded yet.')
      return
    }

    const email = emailInput.trim()
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setEmailStatus('Please enter a valid email address.')
      return
    }

    setIsEmailSending(true)
    try {
      const response = await api.post<SendEmailResponse>(`/project/${projectId}/email`, { email })
      setEmailStatus(response.data.message || 'Plan sent successfully.')
    } catch (err) {
      setEmailStatus('Could not send email. Please check SMTP settings and try again.')
    } finally {
      setIsEmailSending(false)
    }
  }

  async function openDayDetail(roadmapDay: number, date: Date, task: string) {
    if (!projectId) return
    setSelectedDayMeta({
      day: roadmapDay,
      dateLabel: formatShortDate(date),
      task,
    })
    setIsDayModalOpen(true)
    setDayDetail(null)
    setDayDetailError(null)
    setDayDetailLoading(true)

    try {
      const response = await api.get<DayDetailResponse>(`/project/${projectId}/day/${roadmapDay}/detail`)
      setDayDetail(response.data)
    } catch (err) {
      setDayDetailError('Could not load detailed plan for this day. Please try again.')
    } finally {
      setDayDetailLoading(false)
    }
  }

  const score = Math.max(0, Math.min(100, Math.round(result?.seo_score ?? 0)))
  const scoreStyle = useMemo(() => {
    if (score < 40) {
      return {
        ['--score-color' as string]: '#dc2626',
        ['--score-track' as string]: '#f8dada',
      }
    }
    if (score < 70) {
      return {
        ['--score-color' as string]: '#d97706',
        ['--score-track' as string]: '#f8ebcf',
      }
    }
    return {
      ['--score-color' as string]: '#0e9f55',
      ['--score-track' as string]: '#ddf3e4',
    }
  }, [score])

  const activePlanDays = useMemo(() => {
    const roadmap = result?.roadmap ?? []
    if (!roadmap.length) return lastPlanDays
    const maxDay = roadmap.reduce((acc, item) => Math.max(acc, Number(item.day) || 0), 0)
    return Math.max(7, Math.min(30, maxDay || lastPlanDays))
  }, [lastPlanDays, result])

  const planDateItems = useMemo<CalendarPlanItem[]>(() => {
    const roadmap = result?.roadmap ?? []
    const byDay = new Map<number, string>()
    for (const item of roadmap) {
      if (item.day >= 1 && item.day <= activePlanDays && !byDay.has(item.day)) {
        byDay.set(item.day, item.task)
      }
    }

    return Array.from({ length: activePlanDays }, (_, index) => {
      const roadmapDay = index + 1
      return {
        roadmapDay,
        date: addDays(planStartDate, index),
        task: byDay.get(roadmapDay) ?? 'No task assigned.',
      }
    })
  }, [activePlanDays, planStartDate, result])

  const planMonthStarts = useMemo(() => {
    const out: Date[] = []
    const firstDate = planDateItems[0]?.date ?? planStartDate
    const lastDate = planDateItems[planDateItems.length - 1]?.date ?? firstDate
    let cursor = startOfMonth(firstDate)
    const end = startOfMonth(lastDate)

    while (cursor <= end) {
      out.push(new Date(cursor))
      cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1)
    }

    return out
  }, [planDateItems, planStartDate])

  useEffect(() => {
    setCalendarMonthIndex(0)
  }, [activePlanDays, projectId])

  const clampedCalendarMonthIndex = Math.max(0, Math.min(calendarMonthIndex, planMonthStarts.length - 1))
  const currentCalendarMonthStart = planMonthStarts[clampedCalendarMonthIndex] ?? startOfMonth(planStartDate)
  const todayKey = useMemo(() => toDateKey(new Date()), [])

  const calendarCells = useMemo<CalendarCell[]>(() => {
    const year = currentCalendarMonthStart.getFullYear()
    const month = currentCalendarMonthStart.getMonth()
    const firstWeekday = (currentCalendarMonthStart.getDay() + 6) % 7
    const daysInMonth = new Date(year, month + 1, 0).getDate()

    const planByDate = new Map<string, { task: string; roadmapDay: number }>()
    for (const item of planDateItems) {
      planByDate.set(toDateKey(item.date), { task: item.task, roadmapDay: item.roadmapDay })
    }

    const cells: CalendarCell[] = []
    for (let i = 0; i < firstWeekday; i += 1) {
      cells.push({ key: `placeholder-start-${i}`, isPlaceholder: true })
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = new Date(year, month, day)
      const key = toDateKey(date)
      const planItem = planByDate.get(key)

      cells.push({
        key,
        isPlaceholder: false,
        date,
        task: planItem?.task,
        roadmapDay: planItem?.roadmapDay,
        isInPlan: Boolean(planItem),
        isToday: key === todayKey,
      })
    }

    while (cells.length % 7 !== 0) {
      cells.push({ key: `placeholder-end-${cells.length}`, isPlaceholder: true })
    }

    return cells
  }, [currentCalendarMonthStart, planDateItems, todayKey])

  const planWindowLabel = useMemo(() => {
    if (!planDateItems.length) return ''
    const start = planDateItems[0].date
    const end = planDateItems[planDateItems.length - 1].date
    return `${formatShortDate(start)} - ${formatShortDate(end)}`
  }, [planDateItems])

  function goToLanding() {
    setIsDayModalOpen(false)
    setDayDetail(null)
    setDayDetailError(null)
    setView('landing')
    clearProjectIdFromUrl()
  }

  return (
    <div className="app-shell">
      <div className="bg-orb orb-one" />
      <div className="bg-orb orb-two" />
      <header className="topbar">
        <button className="brand-button" onClick={goToLanding} type="button">
          SEOmentor
        </button>
        <div className="topbar-actions">
          <button className="btn btn-ghost topbar-btn" onClick={() => setView('history')} type="button">
            History
          </button>
          <span className="badge">Your AI SEO Co-Founder</span>
        </div>
      </header>

      {view === 'landing' && (
        <main className="panel hero reveal">
          <p className="eyebrow">Smart SEO Intelligence</p>
          <h1>Audit your website and turn insights into real ranking growth.</h1>
          <p className="hero-text">
            SEOmentor audits your homepage, finds realistic competitors, and gives your team
            daily tasks to lift search performance.
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={() => setView('analyze')} type="button">
              Analyze My Website
            </button>
          </div>
        </main>
      )}

      {view === 'analyze' && (
        <main className="panel form-panel reveal">
          <h2>Analyze Website</h2>
          <p>Enter your target website and market to generate a focused SEO plan.</p>
          <form className="analyze-form" onSubmit={handleAnalyzeSubmit}>
            <label>
              Website URL
              <input
                value={form.url}
                onChange={(event) => setForm((prev) => ({ ...prev, url: event.target.value }))}
                placeholder="example.com (https:// is added automatically)"
                type="text"
                required
              />
            </label>
            <div className="field-row">
              <label>
                Country
                <select
                  value={form.country}
                  onChange={(event) => setForm((prev) => ({ ...prev, country: event.target.value }))}
                >
                  {COUNTRY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Language
                <select
                  value={form.language}
                  onChange={(event) => setForm((prev) => ({ ...prev, language: event.target.value }))}
                >
                  {LANGUAGE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="field-row">
              <label>
                Primary Goal
                <select
                  value={form.primary_goal}
                  onChange={(event) => setForm((prev) => ({ ...prev, primary_goal: event.target.value }))}
                  required
                >
                  {GOAL_OPTIONS.map((goal) => (
                    <option key={goal} value={goal}>
                      {goal}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Business Type / Offer
                <input
                  value={form.business_offer}
                  onChange={(event) => setForm((prev) => ({ ...prev, business_offer: event.target.value }))}
                  placeholder="Example: Private university admissions"
                  type="text"
                  required
                />
              </label>
            </div>
            <details className="advanced-panel">
              <summary>Advanced options (optional)</summary>
              <div className="advanced-grid">
                <label>
                  Target Audience
                  <input
                    value={form.target_audience}
                    onChange={(event) => setForm((prev) => ({ ...prev, target_audience: event.target.value }))}
                    placeholder="Example: Students 17-25 in Azerbaijan"
                    type="text"
                  />
                </label>
                <label>
                  Execution Capacity
                  <input
                    value={form.execution_capacity}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, execution_capacity: event.target.value }))
                    }
                    placeholder="Example: 2 blog posts/week, limited dev support"
                    type="text"
                  />
                </label>
                <label>
                  Priority Pages (comma or new line)
                  <textarea
                    value={form.priority_pages}
                    onChange={(event) => setForm((prev) => ({ ...prev, priority_pages: event.target.value }))}
                    placeholder="/, /admissions, /programs/computer-science"
                    rows={3}
                  />
                </label>
                <label>
                  Seed Keywords (comma or new line)
                  <textarea
                    value={form.seed_keywords}
                    onChange={(event) => setForm((prev) => ({ ...prev, seed_keywords: event.target.value }))}
                    placeholder="engineering university azerbaijan, masters in baku"
                    rows={3}
                  />
                </label>
                <label>
                  Known Competitors (comma or new line)
                  <textarea
                    value={form.known_competitors}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, known_competitors: event.target.value }))
                    }
                    placeholder="beu.edu.az, khazar.org"
                    rows={3}
                  />
                </label>
              </div>
            </details>
            <label className="range-field">
              Roadmap Length
              <div className="range-row">
                <input
                  type="range"
                  min={7}
                  max={30}
                  step={1}
                  value={form.plan_days}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, plan_days: Number(event.target.value) }))
                  }
                />
                <strong>{form.plan_days} days</strong>
              </div>
            </label>
            {error && <p className="error-text">{error}</p>}
            <div className="hero-actions">
              <button className="btn btn-primary" disabled={isBusy} type="submit">
                {isBusy ? 'Working...' : 'Run Analysis'}
              </button>
              <button className="btn btn-ghost" onClick={goToLanding} type="button">
                Back
              </button>
            </div>
          </form>
        </main>
      )}

      {view === 'loading' && (
        <main className="panel loading-panel reveal">
          <div className="spinner" />
          <h2>{loadingSteps[loadingStep]}</h2>
          <p>We are building your market-aware SEO roadmap.</p>
        </main>
      )}

      {view === 'history' && (
        <main className="panel history-panel reveal">
          <div className="history-head">
            <div>
              <h2>Analysis History</h2>
              <p>Open any previous report instantly.</p>
            </div>
            <button className="btn btn-ghost" onClick={() => void fetchHistory()} type="button">
              Refresh
            </button>
          </div>

          {historyLoading && <p className="muted">Loading recent projects...</p>}
          {!historyLoading && historyItems.length === 0 && (
            <p className="muted">No reports yet. Run your first analysis.</p>
          )}

          {!historyLoading && historyItems.length > 0 && (
            <div className="history-list">
              {historyItems.map((item) => (
                <button
                  className="history-item"
                  key={item.id}
                  onClick={() => {
                    setProjectId(item.id)
                    setLastPlanDays(Math.max(7, Math.min(30, item.plan_days || 30)))
                    void fetchProject(item.id)
                  }}
                  type="button"
                >
                  <div className="history-main">
                    <h4>{hostnameLabel(item.url)}</h4>
                    <p>{item.url}</p>
                  </div>
                  <div className="history-meta">
                    <span className="history-pill">{Math.round(item.seo_score)} score</span>
                    <span className="history-pill">{item.plan_days} days</span>
                    <span className="history-date">{formatCreatedAt(item.created_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="hero-actions">
            <button className="btn btn-primary" onClick={() => setView('analyze')} type="button">
              New Analysis
            </button>
            <button className="btn btn-ghost" onClick={goToLanding} type="button">
              Back Home
            </button>
          </div>
        </main>
      )}

      {view === 'dashboard' && (
        <main className="dashboard reveal">
          {!result && (
            <section className="panel">
              <p className="muted">
                No dashboard data loaded yet. Run an analysis first to see issues, competitors, and
                your roadmap.
              </p>
            </section>
          )}

          <section className="panel score-panel">
            <div
              className="score-ring"
              style={{ ['--score' as string]: String(score), ...scoreStyle }}
            >
              <div>
                <strong>{score}</strong>
                <span>/100</span>
              </div>
            </div>
            <div>
              <p className="eyebrow">SEO Score</p>
              <h2>Performance Snapshot</h2>
              <p>
                Project ID: <strong>{projectId ?? '-'}</strong>
              </p>
              <p className="muted">
                API: <code>{API_BASE_URL}</code>
              </p>
            </div>
          </section>

          {error && (
            <section className="panel">
              <p className="error-text">{error}</p>
              <button
                className="btn btn-primary"
                onClick={() => (projectId ? void fetchProject(projectId) : setView('analyze'))}
                type="button"
              >
                Try Again
              </button>
            </section>
          )}

          <section className="grid-two">
            <article className="panel card-list">
              <h3>Key Issues</h3>
              <ul>
                {(result?.issues ?? []).map((issue, index) => (
                  <li key={`${issue}-${index}`}>{issue}</li>
                ))}
              </ul>
            </article>

            <article className="panel card-list">
              <h3>Keyword Gaps</h3>
              <ul>
                {(result?.keyword_gaps ?? []).map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </article>
          </section>

          <section className="panel">
            <h3>Competitors</h3>
            <div className="competitor-grid">
              {(result?.competitors ?? []).map((item, index) => (
                <a
                  className="competitor-link"
                  href={competitorHref(item)}
                  key={`${item.name}-${index}`}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  <article className="competitor-card">
                    <h4>{item.name}</h4>
                    <p>{item.reason}</p>
                  </article>
                </a>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="calendar-title-row">
              <h3>Roadmap Calendar</h3>
              <span className="history-pill">{activePlanDays} days</span>
            </div>
            <div className="calendar-toolbar">
              <button
                className="btn btn-ghost calendar-nav"
                disabled={clampedCalendarMonthIndex === 0}
                onClick={() => setCalendarMonthIndex((prev) => Math.max(0, prev - 1))}
                type="button"
              >
                Prev
              </button>
              <p className="calendar-month">{formatMonthYear(currentCalendarMonthStart)}</p>
              <button
                className="btn btn-ghost calendar-nav"
                disabled={clampedCalendarMonthIndex >= planMonthStarts.length - 1}
                onClick={() =>
                  setCalendarMonthIndex((prev) => Math.min(planMonthStarts.length - 1, prev + 1))
                }
                type="button"
              >
                Next
              </button>
            </div>
            {planWindowLabel && <p className="muted calendar-range">Plan window: {planWindowLabel}</p>}
            <p className="muted calendar-range">Click any planned day to view detailed execution steps.</p>
            <div className="calendar-head">
              {WEEKDAY_LABELS.map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>
            <div className="calendar-grid">
              {calendarCells.map((cell) =>
                cell.isPlaceholder ? (
                  <div className="calendar-empty" key={cell.key} />
                ) : cell.isInPlan ? (
                  <button
                    className={`calendar-cell calendar-cell-button is-plan${
                      cell.isToday ? ' is-today' : ''
                    }`}
                    key={cell.key}
                    onClick={() =>
                      void openDayDetail(
                        cell.roadmapDay || 1,
                        cell.date || new Date(),
                        cell.task || 'No task assigned.',
                      )
                    }
                    type="button"
                  >
                    <div className="calendar-cell-top">
                      <span className="calendar-date">{cell.date?.getDate()}</span>
                      <span className="calendar-day">Day {cell.roadmapDay}</span>
                    </div>
                    <p>{cell.task}</p>
                  </button>
                ) : (
                  <article className={`calendar-cell${cell.isToday ? ' is-today' : ''}`} key={cell.key}>
                    <div className="calendar-cell-top">
                      <span className="calendar-date">{cell.date?.getDate()}</span>
                    </div>
                    <p className="calendar-idle">No roadmap task.</p>
                  </article>
                ),
              )}
            </div>
          </section>

          <section className="dashboard-actions">
            <button className="btn btn-primary" onClick={() => setView('analyze')} type="button">
              New Analysis
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                setEmailStatus(null)
                setEmailInput('')
                setIsEmailModalOpen(true)
              }}
              type="button"
            >
              Send PDF by Email
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => (projectId ? void fetchProject(projectId) : setView('analyze'))}
              type="button"
            >
              Refresh
            </button>
          </section>
        </main>
      )}

      {isEmailModalOpen && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (!isEmailSending) {
              setIsEmailModalOpen(false)
            }
          }}
          role="presentation"
        >
          <div className="modal-card" onClick={(event) => event.stopPropagation()} role="dialog">
            <h3>Send Plan PDF</h3>
            <p>Enter the recipient email for this report.</p>
            <form className="analyze-form" onSubmit={handleEmailSend}>
              <label>
                Email Address
                <input
                  autoFocus
                  value={emailInput}
                  onChange={(event) => setEmailInput(event.target.value)}
                  placeholder="you@gmail.com"
                  type="email"
                  required
                />
              </label>
              {emailStatus && (
                <p className={emailStatus.toLowerCase().includes('sent') ? 'success-text' : 'error-text'}>
                  {emailStatus}
                </p>
              )}
              <div className="hero-actions">
                <button className="btn btn-primary" disabled={isEmailSending} type="submit">
                  {isEmailSending ? 'Sending...' : 'Send Plan'}
                </button>
                <button
                  className="btn btn-ghost"
                  disabled={isEmailSending}
                  onClick={() => setIsEmailModalOpen(false)}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isDayModalOpen && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (!dayDetailLoading) {
              setIsDayModalOpen(false)
            }
          }}
          role="presentation"
        >
          <div
            className="modal-card modal-card-wide"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <h3>
              Day {selectedDayMeta?.day ?? '-'} Task Detail
              {selectedDayMeta?.dateLabel ? ` - ${selectedDayMeta.dateLabel}` : ''}
            </h3>
            <p>{selectedDayMeta?.task || 'Daily roadmap task'}</p>
            {dayDetailLoading && <p className="muted">Generating detailed action plan...</p>}
            {dayDetailError && <p className="error-text">{dayDetailError}</p>}

            {!dayDetailLoading && dayDetail && (
              <div className="day-detail-content">
                <p>{dayDetail.description}</p>
                <h4>Checklist</h4>
                <ul className="detail-checklist">
                  {dayDetail.checklist.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
                <p>
                  <strong>KPI:</strong> {dayDetail.kpi}
                </p>
              </div>
            )}

            <div className="hero-actions">
              <button className="btn btn-ghost" onClick={() => setIsDayModalOpen(false)} type="button">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="site-footer">© {new Date().getFullYear()} Team Peak. All rights reserved.</footer>
    </div>
  )
}

export default App
