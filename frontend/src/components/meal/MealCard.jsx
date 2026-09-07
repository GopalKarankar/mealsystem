import { useState } from 'react'
import { formatTime, formatNumber } from '../../utils/formatting'
import Badge from '../common/Badge'
import Button from '../common/Button'
import MealItem from './MealItem'
import Card from '../common/Card'

export default function MealCard({ meal, onUpdate, onDelete }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editItems, setEditItems] = useState(meal.meal_items)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [localError, setLocalError] = useState('')

  const handleSave = async () => {
    if (editItems.length === 0) {
      setLocalError('Must have at least one item')
      return
    }

    setLocalError('')
    setIsSaving(true)

    try {
      const updatedMeal = await onUpdate(meal.meal_id, {
        meal_items: editItems,
      })
      setEditItems(updatedMeal.meal_items)
      setIsEditing(false)
    } catch (err) {
      setLocalError(typeof err === 'string' ? err : 'Failed to save changes')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    setIsDeleting(true)
    try {
      await onDelete(meal.meal_id)
    } catch (err) {
      setLocalError(typeof err === 'string' ? err : 'Failed to delete meal')
      setConfirmingDelete(false)
    } finally {
      setIsDeleting(false)
    }
  }

  const itemPreview = meal.meal_items[0]?.item_name || 'Meal'
  const itemCount = meal.meal_items.length

  return (
    <Card>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1">
            <Badge variant={meal.confidence_badge} />
            <div className="flex-1 min-w-0">
              <p className="font-medium text-primary-black truncate">
                {itemCount === 1 ? itemPreview : `${itemPreview} +${itemCount - 1} more`}
              </p>
              <p className="text-xs text-gray-600">{formatTime(meal.created_at)}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 ml-2">
            <p className="font-bold text-primary-black whitespace-nowrap">{formatNumber(meal.totals.calories)} cal</p>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-2 hover:bg-primary-gray rounded-md transition-colors"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? '▼' : '▶'}
            </button>
          </div>
        </div>

        {isExpanded && (
          <div className="space-y-4 border-t border-primary-border pt-4">
            {isEditing ? (
              <div className="space-y-3">
                {editItems.map((item, idx) => (
                  <MealItem
                    key={idx}
                    item={item}
                    editable={true}
                    onChange={(updated) => {
                      const newItems = [...editItems]
                      newItems[idx] = updated
                      setEditItems(newItems)
                    }}
                  />
                ))}

                {localError && (
                  <div className="p-3 bg-status-error bg-opacity-10 border border-status-error rounded text-status-error text-sm">
                    {localError}
                  </div>
                )}

                <div className="flex gap-2 pt-2">
                  <Button variant="primary" onClick={handleSave} isLoading={isSaving}>
                    Save
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setIsEditing(false)
                      setEditItems(meal.meal_items)
                      setLocalError('')
                    }}
                    disabled={isSaving}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="space-y-3">
                  {meal.meal_items.map((item, idx) => (
                    <MealItem key={idx} item={item} editable={false} />
                  ))}
                </div>

                <div className="bg-primary-gray rounded-md p-4 space-y-2">
                  <p className="font-medium text-primary-black text-sm">Totals</p>
                  <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                    <div>
                      <p className="text-xs text-gray-600">Calories</p>
                      <p className="font-bold text-primary-black">{formatNumber(meal.totals.calories)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Protein</p>
                      <p className="font-bold text-primary-black">{formatNumber(meal.totals.protein_g, 1)}g</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Carbs</p>
                      <p className="font-bold text-primary-black">{formatNumber(meal.totals.carbs_g, 1)}g</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Fats</p>
                      <p className="font-bold text-primary-black">{formatNumber(meal.totals.fats_g, 1)}g</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Fiber</p>
                      <p className="font-bold text-primary-black">{formatNumber(meal.totals.fiber_g, 1)}g</p>
                    </div>
                  </div>
                </div>

                {!confirmingDelete && (
                  <div className="flex gap-2 pt-2">
                    <Button variant="secondary" onClick={() => setIsEditing(true)} className="flex-1">
                      Edit
                    </Button>
                    <Button variant="danger" onClick={() => setConfirmingDelete(true)} className="flex-1">
                      Delete
                    </Button>
                  </div>
                )}

                {confirmingDelete && (
                  <div className="bg-status-error bg-opacity-10 border border-status-error rounded-md p-4">
                    <p className="text-status-error font-medium mb-3">Delete this meal?</p>
                    <div className="flex gap-2">
                      <Button
                        variant="danger"
                        onClick={handleDelete}
                        isLoading={isDeleting}
                        className="flex-1"
                      >
                        Confirm
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => setConfirmingDelete(false)}
                        disabled={isDeleting}
                        className="flex-1"
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
