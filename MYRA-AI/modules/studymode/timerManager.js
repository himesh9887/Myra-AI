class TimerManager {
  constructor({ onTick, onExpire } = {}) {
    this.onTick = typeof onTick === "function" ? onTick : () => {};
    this.onExpire = typeof onExpire === "function" ? onExpire : () => {};
    this._interval = null;
    this._endTime = null;
  }

  start(endTime) {
    this.stop();
    this._endTime = endTime ? new Date(endTime) : null;
    if (!(this._endTime instanceof Date) || Number.isNaN(this._endTime.getTime())) {
      return;
    }

    const tick = () => {
      const remainingSeconds = Math.max(0, Math.round((this._endTime.getTime() - Date.now()) / 1000));
      this.onTick(remainingSeconds, this._endTime.toISOString());
      if (remainingSeconds <= 0) {
        this.stop();
        this.onExpire();
      }
    };

    tick();
    this._interval = setInterval(tick, 1000);
  }

  stop() {
    if (this._interval) {
      clearInterval(this._interval);
      this._interval = null;
    }
    this._endTime = null;
  }

  isRunning() {
    return Boolean(this._interval);
  }
}

module.exports = {
  TimerManager,
};
