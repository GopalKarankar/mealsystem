import MealCard from '../meal/MealCard'
import Spinner from '../common/Spinner'

export default function MealList({ meals, isLoading, error, onUpdate, onDelete }) {
  if (isLoading && meals.length === 0) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    )
  }

  if (error && meals.length === 0) {
    return (
      <div
        role="alert"
        aria-live="polite"
        className="p-6 bg-status-error bg-opacity-10 border border-status-error rounded-lg text-status-error text-sm"
      >
        <p className="font-medium mb-2">{error}</p>
        <p className="text-xs">Please try again or contact support.</p>
      </div>
    )
  }

  if (meals.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-primary-black">No meals logged for this day.</p>
        <p className="text-sm text-gray-600 mt-1">Record one using the button above.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-primary-black">Meals</h2>
      <div className="space-y-3">
        {meals.map((meal) => (
          <MealCard key={meal.meal_id} meal={meal} onUpdate={onUpdate} onDelete={onDelete} />
        ))}
      </div>
    </div>
  )
}
