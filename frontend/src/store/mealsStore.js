import { create } from 'zustand'
import api from '../utils/api'

export const useMealsStore = create((set, get) => ({
  meals: [],
  isLoading: false,
  error: null,
  dailyTotals: {
    calories: 0,
    protein_g: 0,
    carbs_g: 0,
    fats_g: 0,
    fiber_g: 0,
  },
  confidenceDistribution: {
    high: 0,
    medium: 0,
    low: 0,
  },

  fetchMeals: async (date) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get('/meals', { params: { date, limit: 50 } })
      set({ meals: data, isLoading: false })
    } catch (err) {
      set({ error: err.response?.data?.detail || 'Failed to load meals', isLoading: false })
    }
  },

  fetchDashboard: async (date) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get('/dashboard', { params: { date } })
      set({
        dailyTotals: data.daily_totals,
        confidenceDistribution: data.daily_totals.confidence_distribution,
        isLoading: false,
      })
    } catch (err) {
      set({ error: err.response?.data?.detail || 'Failed to load dashboard', isLoading: false })
    }
  },

  addMeal: (meal) => set((state) => ({ meals: [meal, ...state.meals] })),

  updateMeal: async (mealId, payload) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.patch(`/meals/${mealId}`, payload)
      set((state) => ({
        meals: state.meals.map((m) => (m.meal_id === mealId ? data : m)),
        isLoading: false,
      }))
      return data
    } catch (err) {
      set({ isLoading: false })
      throw err.response?.data?.detail || 'Failed to update meal'
    }
  },

  deleteMeal: async (mealId) => {
    set({ isLoading: true, error: null })
    try {
      await api.delete(`/meals/${mealId}`)
      set((state) => ({
        meals: state.meals.filter((m) => m.meal_id !== mealId),
        isLoading: false,
      }))
    } catch (err) {
      set({ isLoading: false })
      throw err.response?.data?.detail || 'Failed to delete meal'
    }
  },

  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),
}))
