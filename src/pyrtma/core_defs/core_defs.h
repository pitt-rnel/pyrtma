
#define MAX_MODULES             200
#define DYN_MOD_ID_START        100
#define MAX_HOSTS               5
#define MAX_MESSAGE_TYPES       10000
#define MIN_STREAM_TYPE         9000
#define MAX_TIMERS              100
#define MAX_INTERNAL_TIMERS     20
#define MAX_RTMA_MSG_TYPE       99
#define MAX_RTMA_MODULE_ID      9
#define MAX_LOGGER_FILENAME_LENGTH  256
#define MAX_CONTIGUOUS_MESSAGE_DATA  9000

//Internal Module IDs
#define MID_MESSAGE_MANAGER     0
#define MID_COMMAND_MODULE      1
#define MID_APPLICATION_MODULE  2
#define MID_NETWORK_RELAY       3
#define MID_STATUS_MODULE       4
#define MID_QUICKLOGGER         5
#define HID_LOCAL_HOST          0
#define HID_ALL_HOSTS           0x7FFF

#define ALL_MESSAGE_TYPES       0x7FFFFFFF


#define MT_EXIT                 0
#define MT_KILL                 1
#define MT_ACKNOWLEDGE          2
#define MT_CONNECT              13
#define MT_DISCONNECT           14
#define MT_SUBSCRIBE            15   
#define MT_UNSUBSCRIBE          16 
#define MT_PAUSE_SUBSCRIPTION   85
#define MT_RESUME_SUBSCRIPTION  86
#define MT_FAIL_SUBSCRIBE       6
#define MT_FAILED_MESSAGE       8
#define MT_FORCE_DISCONNECT    82
#define MT_MODULE_READY         26
#define MT_SAVE_MESSAGE_LOG     56
#define MT_TIMING_MESSAGE       80

typedef short MODULE_ID;
typedef short HOST_ID;
typedef int MSG_TYPE;
typedef int MSG_COUNT;

// Header for messages passed through RTMA
typedef struct {
	MSG_TYPE	msg_type; 
	MSG_COUNT	msg_count;
	double	send_time;
	double	recv_time;
	HOST_ID		src_host_id;
	MODULE_ID	src_mod_id;
	HOST_ID		dest_host_id;
	MODULE_ID	dest_mod_id;
	int			num_data_bytes;
	int			remaining_bytes;
	int			is_dynamic;
	int			reserved;
} RTMA_MSG_HEADER;

typedef struct {
    short logger_status;
    short daemon_status;
} MDF_CONNECT;

typedef struct {
    MSG_TYPE msg_type;
} MDF_SUBSCRIBE;

typedef struct {
    MSG_TYPE msg_type;
} MDF_UNSUBSCRIBE;

typedef struct {
    MSG_TYPE msg_type;
} MDF_PAUSE_SUBSCRIPTION;

typedef struct {
    MSG_TYPE msg_type;
} MDF_RESUME_SUBSCRIPTION;

typedef struct {
    MODULE_ID mod_id;
    short reserved;
    MSG_TYPE msg_type;
} MDF_FAIL_SUBSCRIBE;

typedef struct {
    MODULE_ID dest_mod_id;
    short reserved;
    double time_of_failure;
    RTMA_MSG_HEADER msg_header;
} MDF_FAILED_MESSAGE;

typedef struct {
    int mod_id;
} MDF_FORCE_DISCONNECT;

typedef struct {
    int mod_id;
} MDF_MODULE_READY;

typedef struct {
    char pathname[MAX_LOGGER_FILENAME_LENGTH];
    int pathname_length;
} MDF_SAVE_MESSAGE_LOG;

typedef struct {
    unsigned short timing[MAX_MESSAGE_TYPES];
    int ModulePID[MAX_MODULES];
    double send_time;
} MDF_TIMING_MESSAGE;