#ifndef _INGEST_H
#define _INGEST_H
/*
 * FogLAMP reading ingest.
 *
 * Copyright (c) 2018 OSisoft, LLC
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Mark Riddoch, Massimiliano Pinto, Amandeep Singh Arora
 */
#include <storage_client.h>
#include <reading.h>
#include <logger.h>
#include <vector>
#include <thread>
#include <chrono>
#include <mutex>
#include <sstream>
#include <unordered_set>
#include <condition_variable>
#include <filter_plugin.h>
#include <filter_pipeline.h>
#include <asset_tracking.h>
#include <service_handler.h>

#define SERVICE_NAME  "FogLAMP South"

/**
 * The ingest class is used to ingest asset readings.
 * It maintains a queue of readings to be sent to storage,
 * these are sent using a background thread that regularly
 * wakes up and sends the queued readings.
 */
class Ingest : public ServiceHandler {

public:
	Ingest(StorageClient& storage,
		unsigned long timeout,
		unsigned int threshold,
		const std::string& serviceName,
		const std::string& pluginName,
		ManagementClient *mgmtClient);
	~Ingest();

	void		ingest(const Reading& reading);
	void		ingest(const std::vector<Reading *> *vec);
	bool		running();
	void		processQueue();
	void		waitForQueue();
	size_t		queueLength() { return m_queue->size(); };
	void		updateStats(void);
	int 		createStatsDbEntry(const std::string& assetName);

	bool		loadFilters(const std::string& categoryName);
	static void	passToOnwardFilter(OUTPUT_HANDLE *outHandle,
					   READINGSET* readings);
	static void	useFilteredData(OUTPUT_HANDLE *outHandle,
					READINGSET* readings);

	void		setTimeout(const unsigned long timeout) { m_timeout = timeout; };
	void		setThreshold(const unsigned int threshold) { m_queueSizeThreshold = threshold; };
	void		configChange(const std::string&, const std::string&);
	void		shutdown() {};	// Satisfy ServiceHandler

private:
	StorageClient&			m_storage;
	unsigned long			m_timeout;
	unsigned int			m_queueSizeThreshold;
	bool				m_running;
	std::string 			m_serviceName;
	std::string 			m_pluginName;
	ManagementClient		*m_mgtClient;
	// New data: queued
	std::vector<Reading *>*		m_queue;
	std::mutex			m_qMutex;
	std::mutex			m_statsMutex;
	std::mutex			m_pipelineMutex;
	std::thread*			m_thread;
	std::thread*			m_statsThread;
	Logger*				m_logger;
	std::condition_variable		m_cv;
	std::condition_variable		m_statsCv;
	// Data ready to be filtered/sent
	std::vector<Reading *>*		m_data;
	unsigned int			m_discardedReadings; // discarded readings since last update to statistics table
	FilterPipeline*			m_filterPipeline;
	
	std::unordered_set<std::string>   		statsDbEntriesCache;  // confirmed stats table entries
	std::map<std::string, int>		statsPendingEntries;  // pending stats table entries
};

#endif
