import Redis from 'ioredis';
import { env } from '../config/env.js';
import { logger } from './logger.js';

export const redis = new Redis(env.REDIS_URL, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
});

redis.on('connect', () => logger.info('Redis connected'));
redis.on('error', (err) => logger.error({ err }, 'Redis error'));

export const cache = {
  async get<T>(key: string): Promise<T | null> {
    const data = await redis.get(key);
    return data ? JSON.parse(data) : null;
  },
  async set(key: string, value: unknown, ttlSeconds = 900): Promise<void> {
    await redis.set(key, JSON.stringify(value), 'EX', ttlSeconds);
  },
  async del(key: string): Promise<void> {
    await redis.del(key);
  },
  /**
   * Delete every key matching the glob pattern.
   *
   * Implementation uses SCAN instead of KEYS so Redis stays responsive
   * even when there are millions of keys (KEYS is O(N) and blocks the
   * single-threaded server for the entire duration).
   */
  async invalidatePattern(pattern: string): Promise<void> {
    let cursor = '0';
    const pipeline = redis.pipeline();
    let toDelete = 0;
    do {
      const [nextCursor, batch] = await redis.scan(cursor, 'MATCH', pattern, 'COUNT', 100);
      cursor = nextCursor;
      for (const key of batch) {
        pipeline.del(key);
        toDelete += 1;
      }
    } while (cursor !== '0');

    if (toDelete > 0) {
      await pipeline.exec();
    }
  },
};
