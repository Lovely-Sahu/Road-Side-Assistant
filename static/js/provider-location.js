/*
 * Provider live location (shared by the provider dashboard and the provider's job page).
 *
 * - When the provider taps Accept / On the way / Arrived, the current position is read
 *   and sent WITH that status change, so the driver sees it immediately.
 * - While a job is Accepted / On the way / Arrived and the page is open, the position is
 *   re-sent at most every 10 seconds. The server stops recording once service starts.
 * - The browser's own location permission prompt is the consent; providers can switch
 *   automatic sharing off (remembered in this browser).
 */
(function () {
  'use strict';
  const OPTOUT_KEY = 'rsa-location-optout';
  const TRACKED = ['ACCEPTED', 'ON_THE_WAY', 'ARRIVED'];
  // blocked: the browser refused permission. Do not keep retrying (and re-showing the
  // same error every few seconds) until the page is reloaded.
  let watchId = null, lastSent = 0, blocked = false, onStatus = function () {};

  function optedOut() { try { return localStorage.getItem(OPTOUT_KEY) === '1'; } catch (e) { return false; } }
  function setOptOut(value) { try { localStorage.setItem(OPTOUT_KEY, value ? '1' : '0'); } catch (e) {} }

  function describeError(err) {
    if (!err) return 'Location unavailable.';
    if (err.code === 1) return 'Location is blocked for this site. Click the icon left of the address bar, allow Location, then reload.';
    if (err.code === 3) return 'Getting your location took too long. Check that Windows location is turned on (Settings → Privacy & security → Location).';
    return 'Your device could not determine its location. Turn on Windows location (Settings → Privacy & security → Location) or set a base location manually.';
  }

  function getOnce(timeout) {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) return resolve({ error: { code: 0 }, message: 'This browser cannot share location.' });
      navigator.geolocation.getCurrentPosition(
        function (pos) { resolve({ pos: pos }); },
        function (err) { resolve({ error: err, message: describeError(err) }); },
        { enableHighAccuracy: true, timeout: timeout || 8000, maximumAge: 15000 }
      );
    });
  }

  async function send(pos) {
    const res = await RSA.api('/api/provider/location', { method: 'POST', form: {
      latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy } });
    if (!res.ok) onStatus({ state: 'error', message: res.data.message });
    else if (res.data.tracking_active) onStatus({ state: 'sharing', request: res.data.recorded_for_request, accuracy: pos.coords.accuracy });
    else { onStatus({ state: 'idle' }); stop(); }
    return res;
  }

  function start(callback) {
    if (callback) onStatus = callback;
    if (watchId !== null || optedOut() || blocked) return;
    if (!navigator.geolocation) { onStatus({ state: 'error', message: 'This browser cannot share location.' }); return; }
    watchId = navigator.geolocation.watchPosition(
      function (pos) { if (Date.now() - lastSent < 10000) return; lastSent = Date.now(); send(pos); },
      function (err) {
        onStatus({ state: 'error', message: describeError(err) });
        // Permission refused: stop. Timeout / position unavailable: the watch keeps trying.
        if (err && err.code === 1) { blocked = true; stop(); }
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 }
    );
  }

  function stop() { if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; } }

  /** Change job status; for Accept / On the way / Arrived the current position goes with it. */
  async function changeStatus(matchId, status, note) {
    const form = { status: status, note: note || '' };
    let location = null;
    if (TRACKED.indexOf(status) !== -1 && !optedOut()) {
      location = await getOnce(8000);
      if (location.pos) {
        form.latitude = location.pos.coords.latitude;
        form.longitude = location.pos.coords.longitude;
        form.accuracy = location.pos.coords.accuracy;
        lastSent = Date.now();
      } else if (location.error && location.error.code === 1) {
        blocked = true;
      }
    }
    const res = await RSA.api('/api/provider/job/' + matchId + '/status', { method: 'POST', form: form });
    res.location = location;
    return res;
  }

  function isBlocked() { return blocked; }

  window.RSAProviderLocation = { TRACKED: TRACKED, optedOut: optedOut, setOptOut: setOptOut, start: start, stop: stop,
    changeStatus: changeStatus, isBlocked: isBlocked };
})();
