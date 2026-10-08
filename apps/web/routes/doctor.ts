// `kudbee doctor` for the dashboard: the same checks (doctor.ts), read-only. Network checks only when asked (?online=1), because they take seconds.
import type { Express } from 'express';
import { runDoctor, type DoctorOptions } from '../doctor.ts';
import type { Request } from './types.ts';

export function registerDoctorRoutes(app: Express, deps: Omit<DoctorOptions, 'online'>): void {
  app.get('/api/doctor', async (req: Request, res) => res.json(await runDoctor({ ...deps, online: req.query.online === '1' })));
}
