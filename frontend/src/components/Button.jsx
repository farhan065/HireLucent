import { Link } from 'react-router'

const BASE =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-6 font-display text-[15px] font-bold transition-colors disabled:cursor-not-allowed disabled:bg-line disabled:text-body disabled:shadow-none'

const VARIANTS = {
  primary: 'bg-brand text-white shadow-button hover:bg-brand-dark',
  outline: 'border-[1.5px] border-brand bg-white text-brand hover:bg-tint',
  soft: 'bg-tint text-brand-dark hover:bg-lavender',
  danger: 'bg-danger text-white hover:opacity-90',
}

// Renders a link when "to" is given, otherwise a button.
export default function Button({
  variant = 'primary',
  to,
  type = 'button',
  className = '',
  ...props
}) {
  const classes = `${BASE} ${VARIANTS[variant]} ${className}`
  if (to) return <Link to={to} className={classes} {...props} />
  return <button type={type} className={classes} {...props} />
}