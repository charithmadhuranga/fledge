#ifndef _PERFMONITOR_H
#define _PERFMONITOR_H
/*
 * Fledge performance monitor
 *
 * Copyright (c) 2023 Dianomic Systems
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Mark Riddoch
 */
#include <thread>
#include <storage_client.h>
#include <unordered_map>
#include <insert.h>
#include <mutex>
#include <condition_variable>
#include <housekeeper.h>

class PerformanceMonitor;

/**
 * The individual monitors
 */
class PerfMon {
	public:
		PerfMon(const std::string& name);
		void		addValue(long value);
		int		getValues(InsertValues& values);
	private:
		std::string	m_name;
		long		m_average;
		long		m_min;
		long		m_max;
		int		m_samples;
		std::mutex	m_mutex;
};

/**
 * The housekeeper task used to send the performance monitors
 */
class PerformanceTask : public HouseKeeperTask
{
	public:
		PerformanceTask(PerformanceMonitor *monitor);
		void		run();
		void		cleanup();
	private:
		PerformanceMonitor
				*m_monitor;
};

/**
 * Class to handle the performance monitors
 */
class PerformanceMonitor {
	public:
		PerformanceMonitor(const std::string& service, StorageClient *storage);
		~PerformanceMonitor();
					/**
					 * Collect a performance monitor
					 *
					 * @param name	Name of the monitor
					 * @param calue	Value of the monitor
					 */
		inline void		collect(const std::string& name, long value)
					{
						if (m_collecting)
						{
							doCollection(name, value);
						}
					};
		void			setCollecting(bool state);
		void			writeCounters();
	private:
		void			doCollection(const std::string& name, long value);
	private:
		std::string		m_service;
		StorageClient		*m_storage;
		PerformanceTask		*m_task;
		bool			m_collecting;
		std::unordered_map<std::string, PerfMon *>
					m_monitors;
		std::condition_variable m_cv;
		std::mutex		m_mutex;
};
#endif
