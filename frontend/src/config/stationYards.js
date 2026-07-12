export const stationYardConfig = {
  defaults: {
    signalGuardDistanceM: 260,
    graphPaddingX: 48,
    graphPaddingY: 42,
  },

  // Frontend-local overrides used until the backend provides explicit
  // station_yards / track objects. Keep this layer small and declarative.
  stations: {
    // Example:
    // 'ST-01': {
    //   edgeSegIds: [13, 39, 14, 40],
    //   turnoutIds: ['5', '7'],
    //   signalIds: ['F3', 'XC1'],
    //   tracks: [
    //     { label: 'P1', segIds: [13] },
    //     { label: 'P2', segIds: [39] },
    //   ],
    // },
  },
}

export function getStationYardOverride(stationId) {
  return stationYardConfig.stations?.[stationId] ?? null
}
