// Nutrition calculations and display helpers

function calculateMacroPercentages(totals) {
  const { protein_g, carbs_g, fats_g } = totals;

  const proteinCals = protein_g * 4;
  const carbsCals = carbs_g * 4;
  const fatsCals = fats_g * 9;
  const totalCals = proteinCals + carbsCals + fatsCals;

  if (totalCals === 0) {
    return {
      protein: 0,
      carbs: 0,
      fats: 0,
    };
  }

  return {
    protein: Math.round((proteinCals / totalCals) * 100),
    carbs: Math.round((carbsCals / totalCals) * 100),
    fats: Math.round((fatsCals / totalCals) * 100),
  };
}

function getMacroColor(macroName) {
  const colors = {
    protein: '#FF7043',   // Brand orange
    carbs: '#0369A1',     // Info blue
    fats: '#D97706',      // Gold
    fiber: '#A8B8A8',     // Gray-green
  };
  return colors[macroName] || '#9CA3AF';
}

function getConfidenceColor(score) {
  if (score > 0.90) return '#2E7D32';  // Green
  if (score >= 0.70) return '#FF7043'; // Brand orange
  return '#D64444';                    // Error red
}

function getConfidenceTintClass(score) {
  if (score > 0.90) return 'bg-green-100 text-green-700';
  if (score >= 0.70) return 'bg-orange-100 text-orange-700';
  return 'bg-rose-100 text-rose-700';
}

function formatMacroBreakdown(totals) {
  const percentages = calculateMacroPercentages(totals);
  return {
    protein: {
      grams: Math.round(totals.protein_g * 10) / 10,
      percent: percentages.protein,
      color: getMacroColor('protein'),
    },
    carbs: {
      grams: Math.round(totals.carbs_g * 10) / 10,
      percent: percentages.carbs,
      color: getMacroColor('carbs'),
    },
    fats: {
      grams: Math.round(totals.fats_g * 10) / 10,
      percent: percentages.fats,
      color: getMacroColor('fats'),
    },
    fiber: {
      grams: Math.round(totals.fiber_g * 10) / 10,
      color: getMacroColor('fiber'),
    },
  };
}
