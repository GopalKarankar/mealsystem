import { formatNumber } from '../../utils/formatting'
import Card from '../common/Card'
import Spinner from '../common/Spinner'
import Badge from '../common/Badge'
import MacroChart from './MacroChart'

export default function DailySummary({ date, onDateChange, totals, confidenceDistribution, isLoading }) {
  return (
    <Card>
      <div className="flex flex-col gap-6">
        <div>
          <label htmlFor="date-picker" className="block text-sm font-medium text-primary-black mb-2">
            Date
          </label>
          <input
            id="date-picker"
            type="date"
            value={date}
            onChange={(e) => onDateChange(e.target.value)}
            max={new Date().toISOString().split('T')[0]}
            className="w-full px-4 py-3 border border-primary-border rounded-md bg-primary-white text-primary-black focus:outline-none focus:ring-2 focus:ring-primary-black focus:ring-offset-2"
          />
        </div>

        {isLoading && <Spinner />}

        {!isLoading && (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <div className="bg-primary-gray rounded-md p-4">
                <p className="text-xs font-medium text-primary-black uppercase">Calories</p>
                <p className="text-2xl font-bold text-primary-black mt-1">{formatNumber(totals.calories)}</p>
              </div>
              <div className="bg-primary-gray rounded-md p-4">
                <p className="text-xs font-medium text-primary-black uppercase">Protein</p>
                <p className="text-2xl font-bold text-primary-black mt-1">{formatNumber(totals.protein_g, 1)}g</p>
              </div>
              <div className="bg-primary-gray rounded-md p-4">
                <p className="text-xs font-medium text-primary-black uppercase">Carbs</p>
                <p className="text-2xl font-bold text-primary-black mt-1">{formatNumber(totals.carbs_g, 1)}g</p>
              </div>
              <div className="bg-primary-gray rounded-md p-4">
                <p className="text-xs font-medium text-primary-black uppercase">Fats</p>
                <p className="text-2xl font-bold text-primary-black mt-1">{formatNumber(totals.fats_g, 1)}g</p>
              </div>
              <div className="bg-primary-gray rounded-md p-4">
                <p className="text-xs font-medium text-primary-black uppercase">Fiber</p>
                <p className="text-2xl font-bold text-primary-black mt-1">{formatNumber(totals.fiber_g, 1)}g</p>
              </div>
            </div>

            <div>
              <MacroChart macros={totals} />
            </div>

            <div className="border-t border-primary-border pt-4">
              <p className="text-sm font-medium text-primary-black mb-2">Confidence</p>
              <div className="flex gap-2 flex-wrap">
                <Badge
                  variant="green"
                  label={`High ${confidenceDistribution.high.toFixed(0)}%`}
                />
                <Badge
                  variant="orange"
                  label={`Medium ${confidenceDistribution.medium.toFixed(0)}%`}
                />
                <Badge
                  variant="red"
                  label={`Low ${confidenceDistribution.low.toFixed(0)}%`}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}
