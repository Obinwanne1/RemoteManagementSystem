import { test, expect } from '@playwright/test';

// Requires the API (default http://localhost:5000, or VITE_API_URL) and the
// frontend dev server to be running — see audits/testing_audit.md Finding C6.
// E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD must be a real admin (or superadmin)
// account on whatever backend E2E_BASE_URL points at.
test('admin can log in and see the devices list', async ({ page }) => {
  const email = process.env.E2E_ADMIN_EMAIL;
  const password = process.env.E2E_ADMIN_PASSWORD;
  test.skip(!email || !password, 'E2E_ADMIN_EMAIL/E2E_ADMIN_PASSWORD not set');

  await page.goto('/login');
  await page.getByLabel('Email address').fill(email!);
  await page.getByLabel('Password').fill(password!);
  await page.getByRole('button', { name: /sign in/i }).click();

  await expect(page).toHaveURL(/\/dashboard/);

  await page.goto('/devices');
  await expect(page.getByRole('heading', { name: /devices/i })).toBeVisible();
});

test('wrong password shows an error and does not navigate away from login', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('nobody@e2e-test.invalid');
  await page.getByLabel('Password').fill('definitely-wrong');
  await page.getByRole('button', { name: /sign in/i }).click();

  await expect(page.getByText(/invalid email or password/i)).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});
