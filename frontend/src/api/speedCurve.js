import http from './index'

/**
 * 速度曲线相关 API
 * 对应后端 /api/v1/speedcurve/*
 */

/** 获取所有被追踪的车辆 ID 列表 */
export const getSpeedCurveVehicles = () =>
  http.get('/speedcurve/vehicles', { suppressErrorLog: true })

/** 获取指定车辆当前速度曲线快照 */
export const getSpeedCurveStatus = (vehicleId) =>
  http.get(`/speedcurve/${vehicleId}/status`, { suppressErrorLog: true })

/**
 * 获取指定车辆历史速度曲线数据
 * @param {string} vehicleId
 * @param {number} limit 最多返回点数，默认 300
 */
export const getSpeedCurveHistory = (vehicleId, limit = 300) =>
  http.get(`/speedcurve/${vehicleId}/history`, {
    params: { limit },
    suppressErrorLog: true,
  })

/**
 * 获取前向预测曲线
 * @param {string} vehicleId
 * @param {number} horizonM 预测距离（米），默认 2000
 * @param {number} dtS 积分步长（秒），默认 0.5
 */
export const getSpeedCurvePrediction = (vehicleId, horizonM = 2000, dtS = 0.5) =>
  http.get(`/speedcurve/${vehicleId}/predict`, {
    params: { horizon_m: horizonM, dt_s: dtS },
    suppressErrorLog: true,
  })
