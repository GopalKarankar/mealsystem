import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { calculateMacroPercentages, getMacroColor } from '../../utils/nutrition'

export default function MacroChart({ macros }) {
  const percentages = calculateMacroPercentages(macros)
  const allZero = macros.protein_g === 0 && macros.carbs_g === 0 && macros.fats_g === 0

  if (allZero) {
    return (
      <div className="flex items-center justify-center h-64 bg-primary-gray rounded-md">
        <p className="text-primary-black text-sm">No data to display</p>
      </div>
    )
  }

  const data = [
    { name: 'Protein', value: macros.protein_g * 4, percent: percentages.protein },
    { name: 'Carbs', value: macros.carbs_g * 4, percent: percentages.carbs },
    { name: 'Fats', value: macros.fats_g * 9, percent: percentages.fats },
  ]

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
          <Cell fill={getMacroColor('protein')} />
          <Cell fill={getMacroColor('carbs')} />
          <Cell fill={getMacroColor('fats')} />
        </Pie>
        <Tooltip formatter={(value) => `${value} cal`} />
        <Legend
          formatter={(value) => {
            const item = data.find((d) => d.name === value)
            return `${value} ${item?.percent}%`
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
