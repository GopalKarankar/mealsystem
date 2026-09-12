// Formatting utilities

function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined) return '0';
  return parseFloat(value).toFixed(decimals);
}

function formatTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  const diffTime = today - dateDay;
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    // Today - show time
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } else if (diffDays === 1) {
    return 'Yesterday';
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    // Show date
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
}

function formatDate(dateString, format = 'short') {
  const date = new Date(dateString);
  if (format === 'short') {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
  return date.toLocaleDateString('en-US');
}

function parseISODate(dateString) {
  // Parse YYYY-MM-DD or ISO datetime
  return new Date(dateString);
}

function formatISO(date) {
  // Format as YYYY-MM-DD
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function deriveMealCategoryFromTime(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 7) return 'early_morning';
  if (hour >= 7 && hour < 10) return 'breakfast';
  if (hour >= 10 && hour < 12) return 'mid_morning';
  if (hour >= 12 && hour < 14) return 'lunch';
  if (hour >= 14 && hour < 17) return 'afternoon_snack';
  if (hour >= 17 && hour < 21) return 'dinner';
  return 'bedtime';
}
