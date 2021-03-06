//
//  internalblue-ios-proxy.c
//  internalblue-ios-proxy
//
//  Created by ttdennis on 03.05.19.
//  Copyright © 2019 ttdennis. All rights reserved.
//

#include "internalblue-ios-proxy.h"

#include <stdlib.h>
#include <fcntl.h>
#include <string.h>

#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/errno.h>
#include <sys/select.h>
#include <sys/time.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include <unistd.h>
#include <termios.h>

#define IOAOSSKYSETCHANNELSPEC 0x800C5414
#define IOAOSSKYGETCHANNELUUID 0x40105412

#define CTLIOCGINFO 0xC0644E03

typedef struct ctl_info {
    uint32_t ctl_id;
    char ctl_name[96];
} ctl_info_t;

int btwake_fd, bt_fd;

/*
 This code has been put together by reverse-engineering BlueTool and bluetoothd on
 iOS. Some of the things that happen here are not completely understood but the goal
 was to just get it to work.
 */
int connect_bt_device() {
	int socket_fd = socket(32, 1, 2);
	int error = 0;
	int ret = 0;
	
	struct sockaddr sock_addr;
	struct termios term;
	
	if (socket_fd == 0) {
		printf("[!] Unable to get Bluetooth socket\n");
		return -1;
	}
	
	ctl_info_t *ctl_inf = malloc(sizeof(ctl_info_t));
    ctl_inf->ctl_id = 0;
	strcpy(ctl_inf->ctl_name, "com.apple.uart.bluetooth");
	if ((error = ioctl(socket_fd, CTLIOCGINFO, ctl_inf))) {
		printf("[!] ioctl(CTLIOCGINFO) = %d - errno: %d\n", error, errno);
		printf("[!] error: %s\n", strerror(errno));
		return -1;
	}
	
	*(int *)&sock_addr.sa_len = 0x22020;
	*(int *)&sock_addr.sa_data[2] = ctl_inf->ctl_id;
	ret = connect(socket_fd, &sock_addr, 0x20);
	if (ret != 0) {
		printf("[!] connect() = %d - errno: %d\n", ret, errno);
		printf("[!] error: %s\n", strerror(errno));
		return -1;
	}
	
	printf("[*] Connected to Bluetooth chip H4 socket\n");
	
	socklen_t len = 72;
	
	ret = getsockopt(socket_fd, 2, TIOCGETA, &term, &len);
	if (ret != 0) {
		printf("[!] getsockopt(TIOCGETA) = %d - errno: %d\n", ret, errno);
		printf("[!] error: %s\n", strerror(errno));
		return -1;
	}
	
	cfmakeraw(&term);
	ret = cfsetspeed(&term, 3000000);
	if (ret != 0) {
		printf("[!] cfsetspeed() = %d - errno: %d\n", ret, errno);
		printf("[!] error: %s\n", strerror(errno));
		return -1;
	}
	
	term.c_iflag |= 4;
	term.c_cflag = 232192;
	ret = setsockopt(socket_fd, 2, TIOCSETA, &term, 0x48);
	if (ret != 0) {
		printf("[!] setsockopt() = %d - errno: %d\n", ret, errno);
		printf("[!] error: %s\n", strerror(errno));
		return -1;
	}
	
	tcflush(socket_fd, 3);
	free(ctl_inf);
	
	return socket_fd;
}

int create_server(int port) {
	int server_fd;
	struct sockaddr_in server;
	int on = 1;
	int addrlen;
	
	server_fd = socket(AF_INET, SOCK_STREAM, 0);
	if (server_fd < 0) {
		printf("[!] Unable to create server socket\n");
		return -1;
	}
	
	addrlen = sizeof(server);
	memset(&server, '\0', addrlen);
	server.sin_family = AF_INET;
	server.sin_addr.s_addr = INADDR_ANY;
	server.sin_port = htons(port);
	
	setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &on, 4);
	if (bind(server_fd, (struct sockaddr *)&server, sizeof(server)) < 0) {
		printf("[!] Error binding socket\n");
		return -1;
	}
	
	if (listen(server_fd, 5) < 0) {
		printf("[!] Failed listening on port %d,  Error: %s\n", port, strerror(errno));
		return -1;
	}
	
	printf("[*] Listening on port %d\n", port);
	
	return server_fd;
}

int wait_for_connection(int server_fd) {
	int client_fd;
	socklen_t len;
	struct sockaddr_in client;
	
	len = sizeof(struct sockaddr_in);
	client_fd = accept(server_fd, (struct sockaddr *)&client, (socklen_t *)&len);
	
	if (client_fd < 0) {
		printf("[!] Accepting connection failed\n");
		return -1;
	}
	
	return client_fd;
}

void proxy_bt_socket(int client, int bt) {
	char *client_buf, *bt_buf;
    int nfds, x;
	fd_set R;
	size_t n;
	
	client_buf = malloc(0x2000);
	bt_buf = malloc(0x2000);
	
	nfds = client > bt ? client : bt;
	nfds++;
    
	while(1) {
		struct timeval to;
		FD_ZERO(&R);
        FD_SET(client, &R);
        FD_SET(bt, &R);
		
		to.tv_sec = 0;
		to.tv_usec = 100;
		x = select(nfds+1, &R, 0, 0, &to);
		if (x > 0) {
			if (FD_ISSET(client, &R)) {
                n = read(client, client_buf, 4096);
                if (n > 0) {
                    write(bt, client_buf, n);
                } else {
                    close(client);
                    printf("[!] Client read failed\n");
                    return;
                }
			}
			
			if (FD_ISSET(bt, &R)) {
                n = read(bt, bt_buf, 4096);
                if (n > 0) {
                    write(client, bt_buf, n);
                } else {
                    close(client);
                    printf("[!] H4 socket read failed\n");
                    return;
                }
			}
		} else if (x < 0 && errno != EINTR){
			printf("[!] Select failed with %s\n", strerror(errno));
			close(client);
			return;
		}
		
	}
}

void __exit(int sig) {
	close(bt_fd);
	close(btwake_fd);
	exit(0);
}

int main(int argc, char **argv) {
	int server_fd, client_fd;
	int port;
	
	if (argc != 2) {
		printf("Usage: %s <port_number>\n", argv[0]);
		return 1;
	}
	
	port = atoi(argv[1]);
	
    while (1) {
        // wake BT device
        btwake_fd = open("/dev/btwake", 0);
        
        bt_fd = connect_bt_device();
        if (bt_fd < 0) {
            printf("[!] Error connecting to bluetooth device\n");
            return -1;
        }
        
        server_fd = create_server(port);
        if (server_fd < 0) {
            printf("[!] Unable to create proxy server\n");
            return -1;
        }
        printf("[*] Created proxy server\n");
        
        signal(SIGINT, __exit);
	
		printf("[*] Waiting for remote connection\n");
		client_fd = wait_for_connection(server_fd);
		if (client_fd < 0)
			printf("[!] Unable to connect remote device to proxy\n");
		
        // currently only one connection is supported
		proxy_bt_socket(client_fd, bt_fd);
		close(client_fd);
        close(server_fd);
        close(bt_fd);
        close(btwake_fd);
	}
	
	return 0;
}
