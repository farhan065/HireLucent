import { useState } from 'react'
import { WEIGHT_LABELS } from '../lib/stages.js'

// Turn the saved shape into what the form edits: keywords as one text
// field, weights as whole percentages.
function toForm({ requirements, scoring_weights: weights }) {
  return {
    minExperience: requirements.min_experience_years,
    items: requirements.items.map((item) => ({ ...item, keywords: item.keywords.join(', ') })),
    weights: Object.fromEntries(
      Object.keys(WEIGHT_LABELS).map((key) => [key, Math.round(weights[key] * 100)]),
    ),
  }
}

function fromForm(form) {
  return {
    requirements: {
      min_experience_years: Number(form.minExperience) || 0,
      items: form.items.map((item) => ({
        ...item,
        text: item.text.trim(),
        keywords: item.keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean),
      })),
    },
    scoring_weights: Object.fromEntries(
      Object.keys(WEIGHT_LABELS).map((key) => [key, Number(form.weights[key]) / 100]),
    ),
  }
}

function nextId(items) {
  const numbers = items.map((item) => Number(item.id.slice(1)) || 0)
  return `R${Math.max(0, ...numbers) + 1}`
}

// The state of the requirements and weights form, used on the requirements
// card in the conversation and in the job brief's edit panel. "value"
// returns the form in the shape the backend saves.
export function useRequirementsForm(initial) {
  const [form, setForm] = useState(() => toForm(initial))
  const total = Object.values(form.weights).reduce((sum, value) => sum + Number(value), 0)
  const isValid =
    total === 100 &&
    form.items.length > 0 &&
    form.items.every((item) => item.text.trim().length >= 3)

  function updateItem(id, changes) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => (item.id === id ? { ...item, ...changes } : item)),
    }))
  }

  function addItem() {
    setForm((current) => ({
      ...current,
      items: [
        ...current.items,
        {
          id: nextId(current.items),
          text: '',
          category: 'technical_skills',
          priority: 'preferred',
          keywords: '',
        },
      ],
    }))
  }

  function removeItem(id) {
    setForm((current) => ({
      ...current,
      items: current.items.filter((item) => item.id !== id),
    }))
  }

  function setMinExperience(value) {
    setForm((current) => ({ ...current, minExperience: value }))
  }

  function setWeight(key, value) {
    setForm((current) => ({ ...current, weights: { ...current.weights, [key]: value } }))
  }

  return {
    form,
    total,
    isValid,
    value: () => fromForm(form),
    updateItem,
    addItem,
    removeItem,
    setMinExperience,
    setWeight,
  }
}
