/*
 * Fledge Lazy JSON parser
 *
 * Copyright (c) 2024 Dianomic Systems
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Mark Riddoch
 */
#include <logger.h>
#include <lazyjson.h>
#include <ctype.h>
#include <string.h>

using namespace std;

/**
 * Constructor for use with a char * pointer to a string containing a JSON document
 *
 * @param str	The JSON document we are parsing
 */
LazyJSON::LazyJSON(const char *str) : m_str(str)
{
	skipSpace();
	m_state = new LazyJSONState;
	m_state->inObject = (*m_str == '{');
	m_state->inArray = (*m_str == '[');
	m_state->object = m_str;
	if (m_state->inObject)
	{
		m_state->objectEnd = objectEnd(m_str);
	}
	m_stateStack.push(m_state);
}

/**
 * Constructor for use with a C++ string class reference containing a JSON document
 *
 * @param str	The JSON document we are parsing
 */
LazyJSON::LazyJSON(const string& str) : m_str(str.c_str())
{
	skipSpace();
	m_state = new LazyJSONState;
	m_state->inObject = (*m_str == '{');
	m_state->inArray = (*m_str == '[');
	m_state->object = m_str;
	if (m_state->inObject)
	{
		m_state->objectEnd = objectEnd(m_str);
	}
	m_stateStack.push(m_state);
}

/**
 * Destructor for the LazyJSON parser
 */
LazyJSON::~LazyJSON()
{
	while (! m_stateStack.empty())
	{
		delete m_stateStack.top();
		m_stateStack.pop();
	}
}

/**
 * Return a pointer to the attribute value of a named attribute.
 * Return NULL if the attribute was not in the current object
 *
 * @param name		The key of the attribute to find
 * @return char* 	Pointer to the value of the named key or NULL
 */
const char *LazyJSON::getAttribute(const string& name)
{
	if (!m_state->inObject)
	{
		return NULL;
	}
	int len = name.length();
	m_searchFor.size(len + 3);
	char  *searchFor = m_searchFor.str();
	*searchFor = '"';
	strcpy(&searchFor[1], name.c_str());
	searchFor[len + 1] = '"';
	searchFor[len + 2] = 0;
	const char *p = m_state->object;
	while (p < m_state->objectEnd)
	{
		if (strncmp(p, searchFor, len) == 0)
		{
			// Found the key value
			p += len;
			p += 2;
			while (*p && (isspace(*p) || *p == ':'))
				p++;
			return p;
		}
		p++;
	}
	return NULL;
}

/**
 * Return if the JSON value is null
 *
 * @param p	Point to value in JSON string
 * @return bool	True if value is NULL
 */
bool LazyJSON::isNull(const char *p)
{
	return strncasecmp(p, "NULL", 4) == 0;
}

/**
 * Return if the JSON value is bool
 *
 * @param p	Point to value in JSON string
 * @return bool	True if value is a boolean
 */
bool LazyJSON::isBool(const char *p)
{
	return strncasecmp(p, "TRUE", 4) == 0
		|| strncasecmp(p, "FALSE", 5) == 0;
}

/**
 * Return if the JSON value is true
 *
 * @param p	Point to value in JSON string
 * @return bool	True if value is a true
 */
bool LazyJSON::isTrue(const char *p)
{
	return strncasecmp(p, "TRUE", 4) == 0;
}

/**
 * Return if the JSON value is false
 *
 * @param p	Point to value in JSON string
 * @return bool	True if value is a false
 */
bool LazyJSON::isFalse(const char *p)
{
	return strncasecmp(p, "FALSE", 5) == 0;
}

/**
 * Skip over any white space to the next character
 */
void LazyJSON::skipSpace()
{
	while (*m_str && isspace(*m_str))
	{
		m_str++;
	}
}

/**
 * Position ourselves on the first element in an array, this may be an element,
 * object or another array. This has the side effect of pushing a new state
 * block to the stack.
 *
 * @param p	Position of the '[' character of the array
 * @return char*	First element or NULL
 */
const char *LazyJSON::getArray(const char *p)
{
	if (*p != '[')
	{
		return NULL;	// Not an array
	}
	const char *p1 = p + 1;
	while (*p1 && isspace(*p1))
	{
		p1++;
	}
	if (! *p1)
	{
		return NULL;
	}
	m_state = new LazyJSONState();
	m_stateStack.push(m_state);
	m_state->inObject = false;
	m_state->inArray = true;
	m_state->object = p;
	m_state->objectEnd = objectEnd(p);
	return p1;
}

/**
 * Get the next element in an array given the position of the start
 * of the previous element in the array
 *
 * @param p	Position within an array element
 * @return	Start of next element or NULL
 */
const char *LazyJSON::nextArrayElement(const char *p)
{
	if (!p)
	{
		Logger::getLogger()->error("nextArrayElement called with NULL");
		return NULL;
	}
	int nested = 0, object = 0;
	bool quoted = false, escaped = false;
	while (*p)
	{
		if (*p == '"' && escaped == false)
		{
			quoted = !quoted;
		}
		else if (*p == '\\' && escaped == false)
		{
			escaped = true;
		}
		else if (*p == '{' && escaped == false)
		{
			object++;
		}
		else if (*p == '}' && escaped == false)
		{
			object--;
		}
		else if (quoted == false && *p == '[')
		{
			nested++;
		}
		else if (quoted == false && nested > 0 && *p == ']')
		{
			nested--;
		}
		else if (quoted == false && nested == 0 && *p == ']')
		{
			return NULL;	// End of the array
		}
		else if (quoted == false && nested == 0 && object == 0 && *p == ',')
		{
			escaped = false;
			p++;
			while (*p && isspace(*p))
				p++;
			if (*p)
			{
				return p;
			}
			return NULL;
		}
		else
		{
			escaped = false;
		}
		p++;
	}

	return NULL;
}

/**
 * Return the number of remaining elements in the array
 * @param p	Point to start of an element in the array
 * @return	Numebr of elements
 */
int LazyJSON::getArraySize(register const char *p)
{
	int nested = 0, object = 0, size = 1;
	bool quoted = false, escaped = false;

	while (*p)
	{
		if (*p == '"' && escaped == false)
		{
			quoted = !quoted;
		}
		else if (*p == '\\' && escaped == false)
		{
			escaped = true;
		}
		else if (*p == '{' && escaped == false)
		{
			object++;
		}
		else if (*p == '}' && escaped == false)
		{
			object--;
		}
		else if (quoted == false && *p == '[')
		{
			nested++;
		}
		else if (quoted == false && nested > 0 && *p == ']')
		{
			nested--;
		}
		else if (quoted == false && nested == 0 && *p == ']')
		{
			return size;	// End of the array
		}
		else if (quoted == false && nested == 0 && object == 0 && *p == ',')
		{
			escaped = false;
			p++;
			while (*p && isspace(*p))
				p++;
			if (*p)
			{
				size++;
				p--;	// Process non-space character
			}
			else
			{
				Logger::getLogger()->error("Unterminated array in JSON document, document has trailing ','");
				return -1;
			}
		}
		else
		{
			escaped = false;
		}
		p++;
	}

	Logger::getLogger()->error("Unterminated array in JSON document");
	return -1;
}

/**
 * Position ourselves on the start of an object, we don't actually move
 * the poitner at all, just create the new state.
 * This has the side effect of pushing a new state
 * block to the stack.
 *
 * @param p	Position of the '{' character of the object
 * @return char*	First element or NULL
 */
const char *LazyJSON::getObject(const char *p)
{
	if (*p != '{')
	{
		return NULL;	// Not an array
	}
	m_state = new LazyJSONState();
	m_stateStack.push(m_state);
	m_state->inObject = true;
	m_state->inArray = false;
	m_state->object = p;
	m_state->objectEnd = objectEnd(p);
	return p;
}

/**
 * Given we are positioned at the start of an object, return
 * the raw unparsed JSON object.  The pointer returned points
 * to an internally allocated memory buffer that the caller
 * must not free. This buffer will be overwrriten by the net
 * call to getRawObject.
 *
 * @param p	The start of our object
 * @return char*	The object contents in a malloc'd buffer
 */
char *LazyJSON::getRawObject(const char *p)
{
	const char *end = objectEnd(p);
	int len = 1 + end - p;
	m_rawBuffer.size(len);
	char *rval = m_rawBuffer.str();
	// Copy data dealing with escaping
	register char *p2 = rval;
	bool escaped = false;
	while (*p && p <= end)
	{
		if (*p == '\\' && escaped == false)
		{
			escaped = true;
		}
		else
		{
			*p2++ = *p;
			escaped = false;
		}
		p++;
	}
	*p2 = 0;
	return rval;
}

/**
 * Given we are positioned at the start of an object, return
 * the raw unparsed JSON object.  The pointer returned points
 * to an internally allocated memory buffer that the caller
 * must not free. This buffer will be overwrriten by the net
 * call to getRawObject.
 *
 * @param p	The start of our object
 * @param esc	A character to escape
 * @return char*	The object contents in a malloc'd buffer
 */
char *LazyJSON::getRawObject(const char *p, const char esc)
{
	const char *end = objectEnd(p);
	int len = 3 + end - p;
	m_rawBuffer.size(len);
	char *rval = m_rawBuffer.str();
	// Copy data dealing with escaping
	char *p2 = rval;
	bool escaped = false;
	while (*p && p <= end)
	{
		if (*p == '\\' && escaped == false)
		{
			escaped = true;
		}
		else
		{
			if (*p == esc)
			{
				*p2++ = '\\';
			}
			*p2++ = *p;
			escaped = false;
		}
		p++;
	}
	*p2 = 0;
	return rval;
}

/**
 * Pop an array or object off the stack
 */
void LazyJSON::popState()
{
	if (!m_stateStack.empty())
	{
		delete m_stateStack.top();
		m_stateStack.pop();
	}
}

/**
 * Get the contents of a string value
 *
 * @param p	Pointer to the string to retrieve
 * @return	char* The string content
 */
char *LazyJSON::getString(const char *p)
{
	if (*p == '"')
		p++;
	const char *p1 = p;
	bool escaped = false;
	while (*p1 && (*p1 != '"' || escaped))
	{
		if (*p1 == '\\' && escaped == false)
		{
			escaped = true;
		}
		else
		{
			escaped = false;
		}
		p1++;
	}
	if (*p1 == '"')
	{
		// At end of string
		int len = (p1 - p) + 1;
		char *rval = (char *)malloc(len);
		// Copy data dealing with escaping
		char *p2 = rval;
		escaped = false;
		while (*p && p < p1)
		{
			if (*p == '\\' && escaped == false)
			{
				escaped = true;
			}
			else
			{
				*p2++ = *p;
				escaped = false;
			}
			p++;
		}
		*p2 = 0;
		return rval;
	}
	return NULL;
}

/**
 * Get the contents of an integer value
 *
 * @param p	Pointer to the integer to retrieve
 * @return	long The integer value
 */
long LazyJSON::getInt(const char *p)
{
	long rval = 0, sign = 1;
	if (*p == '-')
	{
		sign = -1;
		p++;
	}
	while (*p && isdigit(*p))
	{
		rval = (rval * 10) + *p - '0';
		p++;
	}
	return rval * sign;
}

/**
 * Get the contents of a string value and populate the
 * supplied LazyJSONBuffer with the string.
 *
 * @param p	Pointer to the string to retrieve
 * @param buffer	A buffer to populate
 * @return	bool	Return true if the string was extracted
 */
bool LazyJSON::getString(const char *p, LazyJSONBuffer& buffer)
{
	if (*p == '"')
		p++;
	const char *p1 = p;
	bool escaped = false;
	while (*p1 && (*p1 != '"' || escaped))
	{
		if (*p1 == '\\' && escaped == false)
		{
			escaped = true;
		}
		else
		{
			escaped = false;
		}
		p1++;
	}
	if (*p1 == '"')
	{
		// At end of string
		int len = (p1 - p) + 1;
		buffer.size(len);
		// Copy data dealing with escaping
		char *p2 = buffer.str();
		escaped = false;
		while (*p && p < p1)
		{
			if (*p == '\\' && escaped == false)
			{
				escaped = true;
			}
			else
			{
				*p2++ = *p;
				escaped = false;
			}
			p++;
		}
		*p2 = 0;
		return true;
	}
	return false;
}

/**
 * Locate the end of an object, passed the start of the object.
 *
 * The start point should be pointing at the '{' character of the object
 * or the '[' character of an array.
 *
 * @param start		Pointer to the start of the object
 * @return char* 	Point to the end of the object or NULL on error
 */
const char *LazyJSON::objectEnd(const char *start)
{
	int nested = 0;
	bool quoted = false, escaped = false;
	char st = '{', ed = '}';
	if (*start == '[')
	{
		st = '[';
		ed = ']';
	}
	while (*start)
	{
		if (*start == '"' && escaped == false)
		{
			quoted = !quoted;
			escaped = false;
		}
		else if (*start == '\\' && escaped == false)
		{
			escaped = true;
		}
		else if (quoted == false && *start == st)
		{
			nested++;
			escaped = false;
		}
		else if (quoted == false && *start == ed)
		{
			escaped = false;
			nested--;
			if (nested == 0)
			{
				return start;
			}
		}
		else
		{
			escaped = false;
		}
		start++;
	}

	return NULL;
}

/**
 * Construct a LazyJSON Buffer to hold string data. We initialise
 * the buffer size to a fixed amount, this will grow during the
 * lifetime of the buffer.
 */
LazyJSONBuffer::LazyJSONBuffer() : m_size(INTERNAL_BUFFER_INIT_LENGTH)
{
	m_str = (char *)malloc(m_size);
}

/**
 * Destroy the buffer and associated memory
 */
LazyJSONBuffer::~LazyJSONBuffer()
{
	if (m_str)
	{
		free(m_str);
	}
}

/**
 * Possibly resize the buffer if the current size is
 * less than the requested size
 *
 * @param size	Requested buffer size
 * @return int	The current size of the buffer
 */
int  LazyJSONBuffer::size(size_t size)
{
	if (size > m_size)
	{
		m_size = size;
		free(m_str);
		m_str = (char *)malloc(size);
	}
	return m_size;
}
