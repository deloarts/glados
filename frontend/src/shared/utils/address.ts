interface AddressParts {
  street?: string | null
  postal_code?: string | null
  city?: string | null
}

/**
 * One-line address such as "Main Street 1, 1010 Vienna". Missing or blank
 * parts are left out together with their separator, so a customer or supplier
 * without an address yields an empty string instead of a stray comma.
 */
export function formatAddress({ street, postal_code, city }: AddressParts): string {
  const place = [postal_code, city].map((part) => part?.trim()).filter(Boolean).join(' ')
  return [street?.trim(), place].filter(Boolean).join(', ')
}
