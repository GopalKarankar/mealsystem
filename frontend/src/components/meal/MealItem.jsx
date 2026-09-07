import { formatMacro } from '../../utils/nutrition'
import { formatNumber } from '../../utils/formatting'

export default function MealItem({ item, editable = false, onChange }) {
  if (!editable) {
    return (
      <div className="border border-primary-border rounded-md p-4 bg-primary-gray">
        <div className="flex justify-between items-start gap-4">
          <div className="flex-1">
            <p className="font-medium text-primary-black">{item.item_name}</p>
            <p className="text-sm text-gray-600 mt-1">
              {formatNumber(item.quantity, 1)} {item.unit}
            </p>
          </div>
          <div className="text-right">
            <p className="font-bold text-primary-black">{formatNumber(item.calories)} cal</p>
            <div className="text-xs text-gray-600 mt-2 space-y-1">
              <p>P: {formatMacro(item.protein_g)}</p>
              <p>C: {formatMacro(item.carbs_g)}</p>
              <p>F: {formatMacro(item.fats_g)}</p>
              <p>Fiber: {formatMacro(item.fiber_g)}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const handleChange = (field, value) => {
    onChange({
      ...item,
      [field]: field.includes('_g') || field === 'quantity' || field === 'calories' ? parseFloat(value) || 0 : value,
    })
  }

  return (
    <div className="border border-primary-border rounded-md p-4 bg-primary-white space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div>
          <label className="text-xs font-medium text-primary-black">Item Name</label>
          <input
            type="text"
            value={item.item_name}
            onChange={(e) => handleChange('item_name', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Qty</label>
          <input
            type="number"
            step="0.1"
            min="0.01"
            value={item.quantity}
            onChange={(e) => handleChange('quantity', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Unit</label>
          <input
            type="text"
            value={item.unit}
            onChange={(e) => handleChange('unit', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Calories</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={item.calories}
            onChange={(e) => handleChange('calories', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Protein (g)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={item.protein_g}
            onChange={(e) => handleChange('protein_g', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Carbs (g)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={item.carbs_g}
            onChange={(e) => handleChange('carbs_g', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Fats (g)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={item.fats_g}
            onChange={(e) => handleChange('fats_g', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-primary-black">Fiber (g)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={item.fiber_g}
            onChange={(e) => handleChange('fiber_g', e.target.value)}
            className="w-full mt-1 px-3 py-2 border border-primary-border rounded text-sm"
          />
        </div>
      </div>
    </div>
  )
}
