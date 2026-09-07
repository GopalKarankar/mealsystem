import { useState, useEffect } from 'react'
import { useMealsStore } from '../store/mealsStore'
import { todayStr } from '../utils/formatting'
import { logout } from '../utils/auth'
import Header from '../components/layout/Header'
import Container from '../components/layout/Container'
import AudioRecorder from '../components/audio/AudioRecorder'
import DailySummary from '../components/dashboard/DailySummary'
import MealList from '../components/dashboard/MealList'
import Toast, { useToast } from '../components/common/Toast'

export default function Dashboard() {
  const [selectedDate, setSelectedDate] = useState(todayStr())
  const { toast, showToast, dismissToast } = useToast()

  const { meals, dailyTotals, confidenceDistribution, isLoading, error, fetchMeals, fetchDashboard, addMeal, updateMeal, deleteMeal } = useMealsStore()

  useEffect(() => {
    Promise.all([fetchDashboard(selectedDate), fetchMeals(selectedDate)])
  }, [selectedDate, fetchDashboard, fetchMeals])

  const handleMealAdded = async (meal) => {
    showToast('success', 'Meal added!')
    addMeal(meal)
    if (selectedDate === todayStr()) {
      await fetchDashboard(selectedDate)
    }
  }

  const handleUpdate = async (mealId, payload) => {
    const updated = await updateMeal(mealId, payload)
    await fetchDashboard(selectedDate)
    return updated
  }

  const handleDelete = async (mealId) => {
    await deleteMeal(mealId)
    await fetchDashboard(selectedDate)
  }

  return (
    <div className="min-h-screen bg-primary-white">
      <Header onLogout={logout} />

      <div className="py-8 space-y-8">
        <Container>
          <AudioRecorder onMealAdded={handleMealAdded} />
        </Container>

        <Container>
          <DailySummary
            date={selectedDate}
            onDateChange={setSelectedDate}
            totals={dailyTotals}
            confidenceDistribution={confidenceDistribution}
            isLoading={isLoading}
          />
        </Container>

        <Container>
          <MealList
            meals={meals}
            isLoading={isLoading}
            error={error}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        </Container>
      </div>

      <Toast toast={toast} onDismiss={dismissToast} />
    </div>
  )
}
