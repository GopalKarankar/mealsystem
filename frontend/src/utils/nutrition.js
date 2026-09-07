export function getConfidenceBadgeFromScore(score) {
  if (score > 0.9) return 'green'
  if (score >= 0.7) return 'orange'
  return 'red'
}

export function calculateMacroPercentages({ protein_g, carbs_g, fats_g }) {
  const proteinCals = protein_g * 4
  const carbsCals = carbs_g * 4
  const fatsCals = fats_g * 9
  const totalCals = proteinCals + carbsCals + fatsCals

  if (totalCals === 0) {
    return { protein: 0, carbs: 0, fats: 0 }
  }

  return {
    protein: Math.round((proteinCals / totalCals) * 100),
    carbs: Math.round((carbsCals / totalCals) * 100),
    fats: Math.round((fatsCals / totalCals) * 100),
  }
}

export function formatMacro(value, decimals = 1) {
  return `${value.toFixed(decimals)}g`
}

export function getMacroColor(macro) {
  const colors = {
    protein: '#F97316',
    carbs: '#3B82F6',
    fats: '#D97706',
  }
  return colors[macro] || '#000000'
}
