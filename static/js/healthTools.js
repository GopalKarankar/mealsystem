function calculateBMI(heightCm, weightKg) {
  const heightM = heightCm / 100;
  const bmi = weightKg / (heightM * heightM);
  let category;
  if (bmi < 18.5) category = 'Underweight';
  else if (bmi < 25) category = 'Normal';
  else if (bmi < 30) category = 'Overweight';
  else category = 'Obese';
  return { bmi: Math.round(bmi * 10) / 10, category };
}

function calculateBodyFat(heightCm, neckCm, waistCm, hipCm, gender) {
  let bodyFat;
  if (gender === 'female') {
    bodyFat = 495 / (1.29579 - 0.35004 * Math.log10(waistCm + hipCm - neckCm) + 0.22100 * Math.log10(heightCm)) - 450;
  } else {
    bodyFat = 495 / (1.0324 - 0.19077 * Math.log10(waistCm - neckCm) + 0.15456 * Math.log10(heightCm)) - 450;
  }
  return Math.round(bodyFat * 10) / 10;
}

document.addEventListener('DOMContentLoaded', () => {
  const bmiBtn = document.getElementById('bmi-calculator-btn');
  const bmiModal = document.getElementById('bmi-modal');
  const bmiCalcBtn = document.getElementById('bmi-calculate-btn');
  if (bmiBtn && bmiModal) {
    bmiBtn.addEventListener('click', () => bmiModal.classList.remove('hidden'));
  }
  if (bmiCalcBtn) {
    bmiCalcBtn.addEventListener('click', () => {
      const h = parseFloat(document.getElementById('bmi-height').value);
      const w = parseFloat(document.getElementById('bmi-weight').value);
      const result = document.getElementById('bmi-result');
      if (!h || !w || h <= 0 || w <= 0) {
        result.textContent = 'Enter valid height and weight';
        return;
      }
      const { bmi, category } = calculateBMI(h, w);
      result.textContent = `BMI: ${bmi} (${category})`;
    });
  }

  const bodyfatBtn = document.getElementById('bodyfat-calculator-btn');
  const bodyfatModal = document.getElementById('bodyfat-modal');
  const bodyfatCalcBtn = document.getElementById('bodyfat-calculate-btn');
  if (bodyfatBtn && bodyfatModal) {
    bodyfatBtn.addEventListener('click', () => bodyfatModal.classList.remove('hidden'));
  }
  if (bodyfatCalcBtn) {
    bodyfatCalcBtn.addEventListener('click', () => {
      const h = parseFloat(document.getElementById('bodyfat-height').value);
      const n = parseFloat(document.getElementById('bodyfat-neck').value);
      const w = parseFloat(document.getElementById('bodyfat-waist').value);
      const hip = parseFloat(document.getElementById('bodyfat-hip').value);
      const gender = document.getElementById('bodyfat-gender').value;
      const result = document.getElementById('bodyfat-result');
      if (!h || !n || !w || (gender === 'female' && !hip) || h <= 0 || n <= 0 || w <= 0) {
        result.textContent = 'Enter valid measurements';
        return;
      }
      const bf = calculateBodyFat(h, n, w, gender === 'female' ? hip : 0, gender);
      result.textContent = `Body Fat: ${bf}%`;
    });
  }
});
