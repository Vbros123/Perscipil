import { useCallback } from 'react'
import {
  Link as WouterLink,
  Redirect,
  Route,
  Router,
  Switch,
  useLocation as useWouterLocation,
  useParams,
} from 'wouter'

export { Redirect, Route, Router, Switch, useParams }

export function Link({ to, href, ...props }) {
  return <WouterLink href={to || href} {...props} />
}

export function NavLink({ to, className, ...props }) {
  const [pathname] = useWouterLocation()
  const isActive = pathname === to || pathname.startsWith(`${to}/`)
  const resolvedClassName = typeof className === 'function' ? className({ isActive }) : className
  return <WouterLink href={to} className={resolvedClassName} {...props} />
}

export function useNavigate() {
  const [, navigate] = useWouterLocation()
  return useCallback((to, options = {}) => {
    navigate(to, { replace: Boolean(options.replace), state: options.state })
  }, [navigate])
}

export function useLocation() {
  const [pathname] = useWouterLocation()
  return {
    pathname,
    search: window.location.search,
    state: window.history.state?.state || null,
  }
}

export function useSearchParams() {
  const [pathname] = useWouterLocation()
  void pathname
  return [new URLSearchParams(window.location.search)]
}
