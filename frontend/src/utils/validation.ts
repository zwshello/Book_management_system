export function validIsbn(value: string): boolean {
  const code = value.replace(/[\s-]/g, '').toUpperCase()
  if (/^\d{9}[\dX]$/.test(code)) {
    const sum = [...code].reduce((total, digit, index) => total + (digit === 'X' ? 10 : Number(digit)) * (10 - index), 0)
    return sum % 11 === 0
  }
  if (/^97[89]\d{10}$/.test(code)) {
    const sum = [...code].reduce((total, digit, index) => total + Number(digit) * (index % 2 === 0 ? 1 : 3), 0)
    return sum % 10 === 0
  }
  return false
}
